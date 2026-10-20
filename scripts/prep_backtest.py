"""Point-in-time inputs for the backtest (no look-ahead).

For every game in the chosen seasons, using ONLY games with a strictly earlier date:
  - each team's current-season cumulative PTS, opponent PTS, possessions, games, mean pace
  - league cumulative ORtg (falls back to the prior season's league ORtg before game 1)
Plus each team's full PRIOR-season ORtg/DRtg/pace, rest days, and 3-games-in-4-nights flag.
Joined to file-A spreads/totals (timing unverified) and the verified game-log scores.

Default seasons = discovery only (2023-24, 2024-25). 2025-26 (confirmation, test once) is NOT
built unless --include-confirmation is passed; do that only when the model is frozen.

Output: data/backtest/pit_games.csv ; run audit: python scripts/prep_backtest.py --audit
"""
import argparse, random
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ALL = ["2022-23", "2023-24", "2024-25", "2025-26"]
A_MAP = {"gs": "GSW", "no": "NOP", "ny": "NYK", "sa": "SAS", "utah": "UTA", "wsh": "WAS"}
WINDOW = {"2023-24": "Discovery", "2024-25": "Discovery", "2025-26": "Confirmation"}


def load_log():
    fr = []
    for s in ALL:
        d = pd.read_csv(ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv"); d["season"] = s; fr.append(d)
    g = pd.concat(fr, ignore_index=True)
    o = g[["GAME_ID", "TEAM_ID", "PTS"]].rename(columns={"TEAM_ID": "OPP_ID", "PTS": "OPP_PTS"})
    g = g.merge(o, on="GAME_ID"); g = g[g.TEAM_ID != g.OPP_ID].copy()
    g["date"] = pd.to_datetime(g.GAME_DATE)
    g["poss"] = g.FGA + 0.44 * g.FTA - g.OREB + g.TOV
    g["pace"] = 48 * g.poss / (g.MIN / 5)
    return g.sort_values(["date", "GAME_ID", "TEAM_ABBREVIATION"]).reset_index(drop=True)


def build(seasons):
    g = load_log()
    T = "TEAM_ABBREVIATION"
    # team cumulative BEFORE this game (same team never plays twice a day)
    for c in ("PTS", "OPP_PTS", "poss", "pace"):
        g["cum_" + c] = g.groupby([T, "season"])[c].cumsum() - g[c]
    g["gp"] = g.groupby([T, "season"]).cumcount()
    g["avg_pace"] = np.where(g.gp > 0, g.cum_pace / g.gp.replace(0, np.nan), 0.0)
    # league cumulative strictly before the date
    day = g.groupby(["season", "date"])[["PTS", "poss"]].sum().groupby(level=0).cumsum()
    day = day.groupby(level=0).shift(1)  # exclude the same day
    day["lg_o"] = 100 * day.PTS / day.poss
    prior_lg = {s: 100 * g[g.season == s].PTS.sum() / g[g.season == s].poss.sum() for s in ALL}
    # prior-season team ratings
    pr = g.groupby(["season", T]).agg(pts=("PTS", "sum"), opp=("OPP_PTS", "sum"), poss=("poss", "sum"), pace=("pace", "mean"))
    pr["o"] = 100 * pr.pts / pr.poss; pr["d"] = 100 * pr.opp / pr.poss
    # rest and 3-in-4
    g["prev"] = g.groupby(T).date.shift(1)
    g["rest"] = ((g.date - g.prev).dt.days - 1).fillna(3).clip(lower=0, upper=3)
    g["n4"] = 0
    for k in (1, 2, 3):  # games by same team 1,2,3 games earlier within the last 3 days
        pk = g.groupby(T).date.shift(k)
        g["n4"] += ((g.date - pk).dt.days <= 3).fillna(False).astype(int)
    g["g3in4"] = (g.n4 >= 2).astype(int)  # this game + 2 earlier inside 4 nights

    # Lines: ESPN core API open/close per book (data/espn_odds/espn_lines_<season>.csv).
    # Reference book = ESPN BET when it has a full line, else DraftKings (ESPN's own book in 2025-26 after ESPN BET ended).
    need = ["spread_open", "spread_close", "total_open", "total_close"]
    A = {}
    for s in seasons:
        e = pd.read_csv(ROOT / "data/espn_odds" / f"espn_lines_{s}.csv")
        e = e.dropna(subset=need)
        for pref, book in enumerate(("ESPN BET", "DraftKings")):
            sub = e[e.provider == book].drop_duplicates(["date", "home", "away"])
            for r in sub.itertuples(index=False):
                k = (r.date, r.home, r.away)
                if k not in A:
                    A[k] = dict(book=book, s_open=r.spread_open, s_close=r.spread_close, t_open=r.total_open, t_close=r.total_close,
                                ml_h_open=r.ml_home_open, ml_h_close=r.ml_home_close, ml_a_open=r.ml_away_open, ml_a_close=r.ml_away_close)

    rows = []
    for gid, grp in g[g.season.isin(seasons)].groupby("GAME_ID"):
        d = grp.date.iloc[0]; s = grp.season.iloc[0]
        h = grp[~grp.MATCHUP.str.contains("@")]
        if len(h) != 1: continue  # neutral-site games with ambiguous home are skipped
        h = h.iloc[0]; a = grp[grp[T] != h[T]].iloc[0]
        key = (d.strftime("%Y-%m-%d"), h[T], a[T])
        if key not in A: continue
        Ln = A[key]
        ps = ALL[ALL.index(s) - 1]
        lg = day.lg_o.get((s, d), np.nan)
        lg = prior_lg[ps] if pd.isna(lg) else lg
        def side(r, pre):
            p = pr.loc[(ps, r[T])]
            return {pre + "gp": int(r.gp), pre + "cum_pts": r.cum_PTS, pre + "cum_opp": r.cum_OPP_PTS,
                    pre + "cum_poss": r.cum_poss, pre + "avg_pace": r.avg_pace,
                    pre + "prior_o": p.o, pre + "prior_d": p.d, pre + "prior_pace": p.pace,
                    pre + "rest": int(r.rest), pre + "g3in4": int(r.g3in4)}
        row = {"season": s, "window": WINDOW[s], "date": key[0], "home": h[T], "away": a[T], **side(h, "h_"), **side(a, "a_"),
               "lg_ortg": lg, "book": Ln["book"], "open_home_spread": Ln["s_open"], "mkt_home_spread": Ln["s_close"],
               "open_total": Ln["t_open"], "mkt_total": Ln["t_close"],
               "ml_home_open": Ln["ml_h_open"], "ml_home_close": Ln["ml_h_close"],
               "ml_away_open": Ln["ml_a_open"], "ml_away_close": Ln["ml_a_close"],
               "home_pts": int(h.PTS), "away_pts": int(a.PTS), "game_id": gid}
        rows.append(row)
    return pd.DataFrame(rows)


def audit(df, n=200):
    """Brute-force recompute point-in-time aggregates for a random sample and compare."""
    g = load_log(); T = "TEAM_ABBREVIATION"; bad = 0
    for i in random.Random(7).sample(range(len(df)), min(n, len(df))):
        r = df.iloc[i]; d = pd.Timestamp(r.date)
        for pre, team in (("h_", r.home), ("a_", r.away)):
            prev = g[(g[T] == team) & (g.season == r.season) & (g.date < d)]
            ok = (len(prev) == r[pre + "gp"] and np.isclose(prev.PTS.sum(), r[pre + "cum_pts"]) and
                  np.isclose(prev.OPP_PTS.sum(), r[pre + "cum_opp"]) and np.isclose(prev.poss.sum(), r[pre + "cum_poss"]))
            bad += not ok
        lg_prev = g[(g.season == r.season) & (g.date < d)]
        if len(lg_prev) and not np.isclose(100 * lg_prev.PTS.sum() / lg_prev.poss.sum(), r.lg_ortg): bad += 1
    print(f"audit: {min(n, len(df))} games, mismatches={bad}")
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-confirmation", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--only-confirmation", action="store_true")
    ap.add_argument("--out", default="pit_games.csv")
    a = ap.parse_args()
    seasons = ["2025-26"] if a.only_confirmation else ["2023-24", "2024-25"] + (["2025-26"] if a.include_confirmation else [])
    df = build(seasons)
    out = ROOT / "data/backtest"; out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / a.out, index=False)
    print(f"{len(df)} games by season:", df.groupby("season").size().to_dict())
    if a.audit: audit(df)
