"""Player profiles for everyone who plays above a minutes threshold.

A player qualifies when, this season, minutes per game >= --min-mpg (default 15) over at least --min-gp games (default 5).
Both are arguments, so the threshold is easy to change. Inputs: player box-score logs (this and last season), the latest
roster snapshot (bio), the team game log (games missed) and the parsed injury reports (current status, times listed).
Outputs: data/profiles/player_profiles.csv (one row per qualifying player) and docs/profiles/players.md (readable, by team).

Everything is descriptive. Nothing here feeds the betting model, and the injury and minutes fields are context, not predictions.
Usage: python scripts/build_profiles.py [--season 2026-27] [--min-mpg 15] [--min-gp 5]
"""
import argparse, re, unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def norm_report(name):          # "Clarke,Brandon" -> "brandonclarke"
    last, _, first = str(name).partition(",")
    return norm(first + last)


def per_game_block(g):
    """Season-to-date numbers from one player's game rows (needs MIN, PTS, REB, AST, STL, BLK, TOV, FGM, FGA, FG3M, FG3A, FTM, FTA)."""
    gp = len(g); mins = g.MIN.sum()
    out = dict(gp=gp, mpg=g.MIN.mean(), pts=g.PTS.mean(), reb=g.REB.mean(), ast=g.AST.mean(), stl=g.STL.mean(), blk=g.BLK.mean(), tov=g.TOV.mean())
    for k in ("PTS", "REB", "AST"):
        out[k.lower() + "_per36"] = 36 * g[k].sum() / mins if mins else np.nan
    out["fg_pct"] = g.FGM.sum() / g.FGA.sum() if g.FGA.sum() else np.nan
    out["fg3_pct"] = g.FG3M.sum() / g.FG3A.sum() if g.FG3A.sum() else np.nan
    out["ft_pct"] = g.FTM.sum() / g.FTA.sum() if g.FTA.sum() else np.nan
    denom = 2 * (g.FGA.sum() + 0.44 * g.FTA.sum())
    out["ts_pct"] = g.PTS.sum() / denom if denom else np.nan
    out["fg3a_rate"] = g.FG3A.sum() / g.FGA.sum() if g.FGA.sum() else np.nan
    out["usage_proxy_per36"] = 36 * (g.FGA.sum() + 0.44 * g.FTA.sum() + g.TOV.sum()) / mins if mins else np.nan
    return out


def build(logs, prior_logs, roster, team_games, inj, min_mpg=15.0, min_gp=5):
    """Returns the profile DataFrame. logs/prior_logs: player game rows; roster: latest roster; team_games: team game rows
    (one per team per game, with TEAM_ABBREVIATION); inj: parsed injury rows (may be empty)."""
    logs = logs.sort_values("GAME_DATE"); rows = []
    team_gp = team_games.groupby("TEAM_ABBREVIATION").GAME_ID.nunique().to_dict()
    ros = roster.set_index("PLAYER_ID") if len(roster) else pd.DataFrame()
    inj_latest, inj_count = {}, {}
    if len(inj):
        inj = inj.copy(); inj["key"] = inj.player.map(norm_report)
        inj["t"] = pd.to_datetime(inj.report_time_et, format="%m/%d/%y %I:%M %p", errors="coerce")
        last = inj.sort_values("t").groupby("key").tail(1)
        inj_latest = {r.key: (r.status, r.game_date, r.reason_on_line) for r in last.itertuples()}
        bad = inj[inj.status.isin(["Out", "Doubtful"])]
        inj_count = bad.groupby("key").game_date.nunique().to_dict()
    for pid, g in logs.groupby("PLAYER_ID"):
        cur = per_game_block(g)
        if cur["mpg"] < min_mpg or cur["gp"] < min_gp: continue
        team = g.iloc[-1].TEAM_ABBREVIATION; name = g.iloc[-1].PLAYER_NAME; key = norm(name)
        row = dict(player_id=pid, player=name, team=team)
        if pid in getattr(ros, "index", []):
            b = ros.loc[pid]
            if isinstance(b, pd.DataFrame): b = b.iloc[0]
            row.update(position=b.POSITION, height_in=b.HEIGHT_IN, weight=b.WEIGHT, age=b.AGE, nba_exp=b.EXP, school=b.SCHOOL, how_acquired=b.HOW_ACQUIRED, on_roster=b.TEAM)
        else:
            row.update(on_roster="not on latest roster snapshot")
        row.update({k: cur[k] for k in ("gp", "mpg", "pts", "reb", "ast", "stl", "blk", "tov", "pts_per36", "reb_per36", "ast_per36",
                                        "fg_pct", "fg3_pct", "ft_pct", "ts_pct", "fg3a_rate", "usage_proxy_per36")})
        row["mpg_last5"] = g.tail(5).MIN.mean(); row["mpg_last10"] = g.tail(10).MIN.mean()
        row["mpg_trend_last10_vs_season"] = row["mpg_last10"] - cur["mpg"]
        row["ts_pct_last10"] = per_game_block(g.tail(10))["ts_pct"]
        tg = team_gp.get(team, np.nan); row["team_games"] = tg; row["games_missed"] = (tg - cur["gp"]) if tg == tg else np.nan
        team_rank = logs[logs.TEAM_ABBREVIATION == team].groupby("PLAYER_ID").MIN.mean().rank(ascending=False)
        row["minutes_rank_on_team"] = int(team_rank.get(pid, np.nan)) if pid in team_rank.index else np.nan
        pg = prior_logs[prior_logs.PLAYER_ID == pid] if len(prior_logs) else prior_logs
        if len(pg):
            p = per_game_block(pg)
            row.update(prior_gp=p["gp"], prior_mpg=p["mpg"], prior_pts_per36=p["pts_per36"], prior_ts_pct=p["ts_pct"], prior_usage_proxy_per36=p["usage_proxy_per36"])
        st = inj_latest.get(key)
        row["latest_injury_status"] = st[0] if st else "none on record"
        row["latest_status_game_date"] = st[1] if st else ""
        row["latest_reason_on_line"] = st[2] if st and isinstance(st[2], str) else ""
        row["times_listed_out_or_doubtful"] = inj_count.get(key, 0)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["team", "mpg"], ascending=[True, False]).reset_index(drop=True)


def to_markdown(df, min_mpg, min_gp, season):
    L = [f"# Player profiles, {season}", "",
         f"Players averaging at least {min_mpg:g} minutes per game over at least {min_gp} games ({len(df)} players). Descriptive only; not used by the betting model.",
         "Per-36 rates and shooting splits are season to date from box scores. `usage proxy` = (FGA + 0.44 FTA + TOV) per 36 minutes. Injury status is the player's latest line on the official report.", ""]
    for team, g in df.groupby("team"):
        L += [f"## {team}", "", "| Player | Pos | Ht | Age | GP (missed) | MPG | last 10 | PTS/REB/AST | PTS/36 | TS% | 3P% | Usage proxy | Last season MPG | Injury status |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in g.itertuples():
            ht = f"{int(r.height_in) // 12}-{int(r.height_in) % 12}" if getattr(r, "height_in", None) == getattr(r, "height_in", None) and r.height_in else ""
            fmt = lambda x, f: (f % x) if x == x and x is not None else ""
            L.append(f"| {r.player} | {getattr(r, 'position', '')} | {ht} | {fmt(getattr(r, 'age', np.nan), '%.0f')} | {r.gp} ({fmt(r.games_missed, '%.0f')}) | {r.mpg:.1f} | {r.mpg_last10:.1f} | "
                     f"{r.pts:.1f}/{r.reb:.1f}/{r.ast:.1f} | {r.pts_per36:.1f} | {fmt(r.ts_pct * 100, '%.1f')} | {fmt(r.fg3_pct * 100, '%.1f')} | {r.usage_proxy_per36:.1f} | "
                     f"{fmt(getattr(r, 'prior_mpg', np.nan), '%.1f')} | {r.latest_injury_status} |")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--season", default="2026-27"); ap.add_argument("--min-mpg", type=float, default=15.0)
    ap.add_argument("--min-gp", type=int, default=5); a = ap.parse_args()
    prev = f"{int(a.season[:4]) - 1}-{a.season[2:4]}"
    rd = lambda p: pd.read_csv(p) if p.exists() and p.stat().st_size > 5 else pd.DataFrame()
    logs = rd(ROOT / f"data/players/player_games_{a.season}.csv"); prior = rd(ROOT / f"data/players/player_games_{prev}.csv")
    roster = rd(ROOT / "data/rosters/roster_latest.csv"); tg = rd(ROOT / f"data/games/team_games_{a.season}_Regular_Season.csv")
    inj = rd(ROOT / "data/injuries/injury_status.csv")
    if len(inj): inj = inj[inj.status != "NOT_YET_SUBMITTED"]
    if logs.empty: raise SystemExit("No player game logs yet for this season.")
    df = build(logs, prior, roster, tg, inj, a.min_mpg, a.min_gp)
    out = ROOT / "data/profiles"; out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "player_profiles.csv", index=False)
    docs = ROOT / "docs/profiles"; docs.mkdir(parents=True, exist_ok=True)
    (docs / "players.md").write_text(to_markdown(df, a.min_mpg, a.min_gp, a.season), encoding="utf-8")
    print(f"{len(df)} profiles ({a.min_mpg:g}+ mpg, {a.min_gp}+ games) across {df.team.nunique()} teams, as of {datetime.now(ZoneInfo('America/New_York')):%Y-%m-%d %H:%M}")


if __name__ == "__main__":
    main()
