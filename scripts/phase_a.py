"""Phase A exploratory analysis (descriptive only). See docs/Live_Study_Plan.md.

HARD GUARD: refuses a cutoff after 2026-12-15 so Phase B data (from 2026-12-16) cannot be analysed here.
Everything is filtered to date <= cutoff. No betting claims come out of this script.

Pipeline:
  events  = rotation players (typical minutes when playing >= MIN_MINUTES over the team's last 25 games) who are
            NEWLY Out/Doubtful for a game, i.e. not Out/Doubtful in the final report before the team's previous game.
  response= change in the consensus (median) home spread from the last poll before the report to the first poll after,
            signed so that + means the line moved the way the news implies.
  stale   = at the first poll after the report, how much better the best BETTABLE-book price for the news side is
            than the consensus line at the last poll before tip (+ = would have beaten the consensus close).
Usage: python scripts/phase_a.py --cutoff 2026-12-15
"""
import argparse, re, unicodedata
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PHASE_A_END = "2026-12-15"
MIN_MINUTES = 20.0
BETTABLE = ["bovada", "betonlineag", "mybookieag", "betus", "lowvig"]   # per docs/Live_Study_Plan.md section 5


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def norm_report(name):          # "Clarke,Brandon" -> "brandonclarke"
    last, _, first = str(name).partition(",")
    return norm(first + last)


def et_to_utc(series):
    return pd.to_datetime(series, format="%m/%d/%y %I:%M %p").dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")


def find_events(inj, players, cutoff, min_minutes=MIN_MINUTES, window=25):
    """inj: injury_status rows; players: player game logs (needs PLAYER_NAME, TEAM_ABBREVIATION, GAME_DATE, MIN)."""
    inj = inj[inj.status.isin(["Out", "Doubtful"]) | inj.status.isin(["Questionable", "Probable", "Available"])].copy()
    inj["t_utc"] = et_to_utc(inj.report_time_et)
    inj["gdate"] = pd.to_datetime(inj.game_date, format="%m/%d/%Y")
    inj = inj[inj.gdate <= pd.Timestamp(cutoff)]
    inj["key"] = inj.player.map(norm_report)
    pl = players.copy(); pl["key"] = pl.PLAYER_NAME.map(norm); pl["gdate"] = pd.to_datetime(pl.GAME_DATE); pl["min"] = pl.MIN.astype(float)
    team_games = pl[["TEAM_ABBREVIATION", "gdate", "GAME_ID"]].drop_duplicates()
    rows = []
    bad = inj[inj.status.isin(["Out", "Doubtful"])]
    for (team, gdate, key), g in bad.groupby(["team", "gdate", "key"]):
        first = g.sort_values("t_utc").iloc[0]
        prev_games = team_games[(team_games.TEAM_ABBREVIATION == team) & (team_games.gdate < gdate)].sort_values("gdate")
        # previous team game's final status
        if len(prev_games):
            pg = prev_games.iloc[-1]
            prev = inj[(inj.team == team) & (inj.gdate == pg.gdate) & (inj.key == key)]
            if len(prev) and prev.sort_values("t_utc").iloc[-1].status in ("Out", "Doubtful"):
                continue   # not new: already out last game
        last_ids = prev_games.tail(window).GAME_ID
        mine = pl[(pl.TEAM_ABBREVIATION == team) & (pl.key == key) & pl.GAME_ID.isin(last_ids)]
        if len(mine) < 3: continue
        typical = mine["min"].mean()
        if typical < min_minutes: continue
        away, home = first.matchup.split("@")
        rows.append(dict(game_date=gdate.strftime("%Y-%m-%d"), team=team, home=home, away=away, player=first.player,
                         status=first.status, typical_min=round(typical, 1), report_utc=first.t_utc, report_time_et=first.report_time_et,
                         news_side="away" if team == home else "home"))
    return pd.DataFrame(rows)


def consensus_table(odds):
    """odds: odds_archive rows. Returns per (event, snapshot): median home spread and per-book home spread."""
    s = odds[(odds.market == "spreads") & (odds.outcome == "home")].copy()
    s["cap"] = pd.to_datetime(s.captured_utc, utc=True)
    return s


def evaluate_events(events, odds, bettable=BETTABLE):
    sp = consensus_table(odds); out = []
    for e in events.itertuples(index=False):
        g = sp[(sp.game_date_et == e.game_date) & (sp.home == e.home) & (sp.away == e.away)]
        if g.empty: out.append({**e._asdict(), "status_note": "no odds for game"}); continue
        snaps = sorted(g.cap.unique()); rep = pd.Timestamp(e.report_utc)
        before = [t for t in snaps if t < rep]; after = [t for t in snaps if t >= rep]
        if not before or not after: out.append({**e._asdict(), "status_note": "no poll before or after report"}); continue
        pre, post = before[-1], after[0]
        cons = lambda t: g[g.cap == t].point.median()
        sign = 1 if e.news_side == "away" else -1      # home spread rises when the home side is weakened
        resp = sign * (cons(post) - cons(pre))
        # last poll before tip
        tip = pd.Timestamp(g.commence_time_utc.iloc[0])
        pre_tip = [t for t in snaps if t < tip]
        row = {**e._asdict(), "status_note": "ok", "pre_poll": pre, "post_poll": post, "consensus_pre": cons(pre),
               "consensus_post": cons(post), "response_pts": resp, "polls_between_hours": (post - pre).total_seconds() / 3600}
        if pre_tip:
            close_c = cons(pre_tip[-1]); row["consensus_close"] = close_c
            gb = g[(g.cap == post) & g.book.isin(bettable)]
            if len(gb):
                best = gb.point.min() if e.news_side == "away" else gb.point.max()   # best number for a bettor on the news side
                row["best_bettable_post"] = best
                row["stale_gap_pts"] = (close_c - best) if e.news_side == "away" else (best - close_c)
            allb = g[g.cap == post]
            if len(allb): row["book_lag_dev"] = {b: sign * (v - close_c) for b, v in zip(allb.book, allb.point)}
        out.append(row)
    return pd.DataFrame(out)


def summarize(ev, coverage):
    ok = ev[ev.status_note == "ok"] if len(ev) else ev
    L = ["# Phase A report (descriptive only, not a test)", "", f"Events found: {len(ev)}; evaluable (poll before and after report): {len(ok)}", ""]
    L += ["## Coverage"] + [f"- {k}: {v}" for k, v in coverage.items()] + [""]
    if len(ok):
        L += ["## Line response", f"- mean consensus move in the news direction between polls: {ok.response_pts.mean():+.2f} pts (median {ok.response_pts.median():+.2f}); share of events with any move: {(ok.response_pts.abs() > 0).mean():.0%}",
              f"- median hours between the two polls: {ok.polls_between_hours.median():.1f}"]
        if "stale_gap_pts" in ok:
            sg = ok.stale_gap_pts.dropna()
            L += ["", "## Stale price at bettable books (best bettable number at first poll after report vs consensus line at last poll before tip)",
                  f"- events with data: {len(sg)}; mean {sg.mean():+.2f} pts; share positive {(sg > 0).mean():.0%}; share >= 0.5: {(sg >= 0.5).mean():.0%}",
                  "- Positive means a bettor on the news side would have beaten the consensus close. Descriptive only; the Phase B test is separate."]
        if "book_lag_dev" in ok:
            dev = {}
            for d in ok.book_lag_dev.dropna():
                for b, v in d.items(): dev.setdefault(b, []).append(v)
            L += ["", "## Book lag (news-direction deviation from consensus close at first poll after report; negative = book lagging)"]
            L += [f"- {b}: mean {np.mean(v):+.2f} (n={len(v)})" for b, v in sorted(dev.items(), key=lambda kv: np.mean(kv[1]))]
        L += ["", "## By typical minutes"]
        ok = ok.assign(bucket=pd.cut(ok.typical_min, [0, 25, 30, 48], labels=["20-25", "25-30", "30+"]))
        for b, g in ok.groupby("bucket", observed=True): L.append(f"- {b} min: n={len(g)}, mean response {g.response_pts.mean():+.2f}")
    else:
        L.append("No evaluable events yet.")
    L += ["", "Not run in Phase A: v2 coefficient stability (needs about 30 game days of true reports); all inference is for Phase B."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cutoff", required=True); a = ap.parse_args()
    if a.cutoff > PHASE_A_END:
        raise SystemExit(f"Refused: cutoff {a.cutoff} is after {PHASE_A_END}. Phase B data stays blind until the pre-registered analysis.")
    inj = pd.read_csv(ROOT / "data/injuries/injury_status.csv")
    inj = inj[inj.status != "NOT_YET_SUBMITTED"]
    odds = pd.read_csv(ROOT / "data/odds/odds_archive.csv")
    odds = odds[odds.game_date_et <= a.cutoff]
    pf = ROOT / "data/players/player_games_2026-27.csv"
    players = pd.concat([pd.read_csv(f) for f in sorted((ROOT / "data/players").glob("player_games_202[56]-2*.csv"))], ignore_index=True) if pf.exists() else pd.DataFrame()
    cov = {"cutoff": a.cutoff, "odds snapshots used": odds.captured_utc.nunique() if len(odds) else 0,
           "game dates with odds": odds.game_date_et.nunique() if len(odds) else 0, "injury report rows with a player status": len(inj)}
    ev = pd.DataFrame()
    if len(inj) and len(players):
        ev = evaluate_events(find_events(inj, players, a.cutoff), odds)
    out = ROOT / "docs/phase_a"; out.mkdir(parents=True, exist_ok=True)
    (out / f"report_{a.cutoff}.md").write_text(summarize(ev, cov))
    ev.to_csv(out / f"events_{a.cutoff}.csv", index=False)
    print(summarize(ev, cov))


if __name__ == "__main__":
    main()
