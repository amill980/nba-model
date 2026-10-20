"""Daily projections report: frozen v1 model vs the latest market snapshot. DESCRIPTIVE, NOT A RECOMMENDATION.

The v1 model failed its signed 2025-26 confirmation (docs/Confirmation_Results.md): it has no demonstrated edge.
This report only shows what the model says next to what the market says, with the 1.5-point flag the workbook uses.

Inputs : data/odds/odds_archive.csv (latest snapshot per game), team game logs, parsed injury reports.
Output : docs/daily/projections_<date>.md and .csv
Usage  : python scripts/daily_projections.py [--date YYYY-MM-DD]   (default: tomorrow, ET; today if --today)
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
# frozen v1 parameters (Assumptions tab; tuned on 2023-24 and 2024-25 only)
K, HCA, REST_COEF, REST_CAP, FATIGUE, MIN_EDGE = 10, 1.94, 1.35, 3, -0.59, 1.5
CUR, PRIOR = "2026-27", "2025-26"
BETTABLE = ["bovada", "betonlineag", "mybookieag", "betus", "lowvig"]


def team_table(season):
    p = ROOT / "data/games" / f"team_games_{season}_Regular_Season.csv"
    if not p.exists() or p.stat().st_size < 5: return pd.DataFrame(), pd.DataFrame()
    g = pd.read_csv(p)
    if g.empty: return g, pd.DataFrame()
    o = g[["GAME_ID", "TEAM_ID", "PTS"]].rename(columns={"TEAM_ID": "OID", "PTS": "OPP"})
    g = g.merge(o, on="GAME_ID"); g = g[g.TEAM_ID != g.OID].copy()
    g["poss"] = g.FGA + 0.44 * g.FTA - g.OREB + g.TOV; g["pace"] = 48 * g.poss / (g.MIN / 5)
    t = g.groupby("TEAM_ABBREVIATION").agg(gp=("PTS", "size"), pts=("PTS", "sum"), opp=("OPP", "sum"), poss=("poss", "sum"), pace_sum=("pace", "sum"))
    return g, t


def ratings():
    gp_, tp = team_table(PRIOR); gc, tc = team_table(CUR)
    prior = pd.DataFrame({"po": 100 * tp.pts / tp.poss, "pd": 100 * tp.opp / tp.poss, "pp": tp.pace_sum / tp.gp})
    lg_prior = 100 * tp.pts.sum() / tp.poss.sum()
    lg = 100 * tc.pts.sum() / tc.poss.sum() if len(tc) and tc.poss.sum() > 0 else lg_prior
    out = prior.copy(); out["gp"] = 0; out["co"] = 0.0; out["cd"] = 0.0; out["cp"] = 0.0
    if len(tc):
        c = tc.reindex(out.index)
        out["gp"] = c.gp.fillna(0); out["co"] = (100 * c.pts / c.poss).fillna(0); out["cd"] = (100 * c.opp / c.poss).fillna(0); out["cp"] = (c.pace_sum / c.gp).fillna(0)
    out["bo"] = (K * out.po + out.gp * out.co) / (K + out.gp); out["bd"] = (K * out.pd + out.gp * out.cd) / (K + out.gp)
    out["bp"] = (K * out.pp + out.gp * out.cp) / (K + out.gp)
    return out, lg, gc


def rest_info(gc, team, day):
    """rest days (cap 3) and 3rd-game-in-4-nights flag from this season's games before `day`."""
    if gc is None or len(gc) == 0: return REST_CAP, 0
    d = pd.to_datetime(gc[gc.TEAM_ABBREVIATION == team].GAME_DATE); d = d[d < pd.Timestamp(day)].sort_values()
    if d.empty: return REST_CAP, 0
    rest = int(min(max((pd.Timestamp(day) - d.iloc[-1]).days - 1, 0), REST_CAP))
    last2 = d.iloc[-2] if len(d) >= 2 else None
    return rest, int(last2 is not None and (pd.Timestamp(day) - last2).days <= 3)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date"); ap.add_argument("--today", action="store_true"); a = ap.parse_args()
    now = datetime.now(ET)
    day = a.date or ((now if a.today else now + timedelta(days=1)).strftime("%Y-%m-%d"))
    R, lg, gc = ratings()
    odds = pd.read_csv(ROOT / "data/odds/odds_archive.csv")
    odds = odds[odds.game_date_et == day]
    if odds.empty:
        raise SystemExit(f"No odds in the archive for {day}. The odds task polls only on game days; run it or wait for the next poll.")
    snap = odds.captured_utc.max()
    odds = odds[odds.captured_utc == odds.groupby("event_id").captured_utc.transform("max")]
    inj_path = ROOT / "data/injuries/injury_status.csv"
    inj = pd.read_csv(inj_path) if inj_path.exists() else pd.DataFrame()
    rows = []
    for (eid, home, away, commence), g in odds.groupby(["event_id", "home", "away", "commence_time_utc"]):
        h, w = R.loc[home], R.loc[away]
        pace = (h.bp + w.bp) / 2
        hp = pace * (h.bo + w.bd - lg) / 100; ap_ = pace * (w.bo + h.bd - lg) / 100
        hr, hf = rest_info(gc, home, day); ar, af = rest_info(gc, away, day)
        margin = hp - ap_ + HCA + REST_COEF * np.clip(hr - ar, -REST_CAP, REST_CAP) + (hf - af) * FATIGUE
        total = hp + ap_
        sp = g[(g.market == "spreads") & (g.outcome == "home")]; tt = g[(g.market == "totals") & (g.outcome == "Over")]
        cons_s = sp.point.median() if len(sp) else np.nan; cons_t = tt.point.median() if len(tt) else np.nan
        s_edge = margin + cons_s; t_edge = total - cons_t
        s_side = "HOME" if s_edge >= MIN_EDGE else ("AWAY" if s_edge <= -MIN_EDGE else "no flag")
        t_side = "OVER" if t_edge >= MIN_EDGE else ("UNDER" if t_edge <= -MIN_EDGE else "no flag")
        def best(side):
            b = sp[sp.book.isin(BETTABLE)]
            if b.empty or side == "no flag": return ""
            r = b.loc[b.point.idxmax()] if side == "HOME" else b.loc[b.point.idxmin()]
            num = r.point if side == "HOME" else -r.point
            return f"{r.book} {num:+g} ({int(r.price):+d})"
        def best_t(side):
            t = g[(g.market == "totals") & (g.outcome == ("Over" if side == "OVER" else "Under")) & g.book.isin(BETTABLE)]
            if t.empty or side == "no flag": return ""
            r = t.loc[t.point.idxmin()] if side == "OVER" else t.loc[t.point.idxmax()]
            return f"{r.book} {r.point:g} ({int(r.price):+d})"
        def book_line(b):
            s = sp[sp.book == b]; t = tt[tt.book == b]
            return (f"{s.point.iloc[0]:+g}" if len(s) else "-") + " / " + (f"{t.point.iloc[0]:g}" if len(t) else "-")
        notes = ""
        if len(inj):
            x = inj[(inj.team.isin([home, away])) & inj.status.isin(["Out", "Doubtful"]) & (pd.to_datetime(inj.game_date, format="%m/%d/%Y").dt.strftime("%Y-%m-%d") == day)]
            if len(x): notes = "; ".join(sorted({f"{r.team} {r.player} {r.status}" for r in x.itertuples()}))
        tip = pd.Timestamp(commence).tz_convert(ET).strftime("%I:%M %p")
        rows.append({"tip_et": tip, "game": f"{away} @ {home}", "model_home_margin": round(margin, 1), "model_total": round(total, 1),
                     "consensus_home_spread": cons_s, "consensus_total": cons_t, "spread_edge": round(s_edge, 1), "spread_flag": s_side,
                     "best_bettable_spread": best(s_side), "total_edge": round(t_edge, 1), "total_flag": t_side, "best_bettable_total": best_t(t_side),
                     "bovada_spread_total": book_line("bovada"), "draftkings_spread_total": book_line("draftkings"),
                     "games_played_home_away": f"{int(h.gp)}/{int(w.gp)}", "injury_report_out": notes})
    df = pd.DataFrame(rows).sort_values("tip_et", key=lambda s: pd.to_datetime(s, format="%I:%M %p"))
    out = ROOT / "docs/daily"; out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"projections_{day}.csv", index=False)
    L = [f"# NBA projections for {day}", "",
         "**NOT A RECOMMENDATION. The v1 model has no demonstrated edge**: it failed its signed 2025-26 confirmation test and wins about 50% against the closing line. This page only shows the model next to the market.",
         f"Market = median across all books in the snapshot taken {snap} UTC; lines move, so re-run closer to tip. Flag threshold: {MIN_EDGE} points (workbook default, not tuned).",
         "Early season: ratings are almost entirely last season's (shrinkage K=10) until teams have played several games. Injuries are shown for information only; the model does not use them.", "",
         "| Tip (ET) | Game | Model margin (home +) | Market spread (home) | Spread edge | Spread flag | Best bettable | Model total | Market total | Total edge | Total flag | Best bettable | Bovada s/t | DraftKings s/t | Out/Doubtful |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples():
        L.append(f"| {r.tip_et} | {r.game} | {r.model_home_margin:+.1f} | {r.consensus_home_spread:+g} | {r.spread_edge:+.1f} | {r.spread_flag} | {r.best_bettable_spread} | "
                 f"{r.model_total:.1f} | {r.consensus_total:g} | {r.total_edge:+.1f} | {r.total_flag} | {r.best_bettable_total} | {r.bovada_spread_total} | {r.draftkings_spread_total} | {r.injury_report_out} |")
    L += ["", "Spread flag HOME/AWAY = the side the model prefers by at least the threshold; OVER/UNDER likewise for totals. Home spread is in book notation (negative = home favored)."]
    (out / f"projections_{day}.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
