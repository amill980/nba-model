"""Point-in-time opponent-adjusted team ratings (ridge regression, no look-ahead).

For a game on date D in season S, ratings use ONLY games of season S with date < D:
    y = 100 * PTS / possessions   (one row per team-game, from the offence's side)
    y = mu + off[team] + def[opponent] + hfa * is_home + noise
ridge penalty `lam` on off/def (shrinks toward league average); intercept and hfa unpenalised.
Outputs, per (season, date, team):
    cur_o = mu + off[team]   points scored per 100 poss vs an average defence
    cur_d = mu + def[team]   points allowed per 100 poss vs an average offence  (higher = worse defence)
Prior-season ratings: the same fit on ALL games of the prior season (end-of-season, legitimately known).

Usage: python scripts/opp_adjust.py [--lam 5] [--audit]   -> data/backtest/adj_current_<lam>.csv, adj_prior_<lam>.csv
"""
import argparse, random
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ALL = ["2022-23", "2023-24", "2024-25", "2025-26"]
T = "TEAM_ABBREVIATION"


def load():
    fr = []
    for s in ALL:
        d = pd.read_csv(ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv"); d["season"] = s; fr.append(d)
    g = pd.concat(fr, ignore_index=True)
    o = g[["GAME_ID", T, "TEAM_ID"]].rename(columns={T: "OPP", "TEAM_ID": "OPP_ID"})
    g = g.merge(o, on="GAME_ID"); g = g[g.TEAM_ID != g.OPP_ID].copy()
    g["date"] = pd.to_datetime(g.GAME_DATE)
    g["poss"] = g.FGA + 0.44 * g.FTA - g.OREB + g.TOV
    g["y"] = 100 * g.PTS / g.poss
    g["home"] = (~g.MATCHUP.str.contains("@")).astype(float)
    return g


def fit(rows, teams, lam):
    """rows: dataframe with columns T (offence), OPP (defence), home, y. Returns mu, hfa, off{}, def{}."""
    n = len(teams); idx = {t: i for i, t in enumerate(teams)}
    X = np.zeros((len(rows), 2 * n + 2))
    X[np.arange(len(rows)), rows[T].map(idx).values] = 1
    X[np.arange(len(rows)), n + rows.OPP.map(idx).values] = 1
    X[:, 2 * n] = rows.home.values; X[:, 2 * n + 1] = 1.0
    P = np.diag([lam] * (2 * n) + [0.0, 0.0])
    beta = np.linalg.solve(X.T @ X + P, X.T @ rows.y.values)
    off = dict(zip(teams, beta[:n])); dfn = dict(zip(teams, beta[n:2 * n]))
    return beta[2 * n + 1], beta[2 * n], off, dfn


def build(lam):
    g = load(); teams = sorted(g[T].unique()); cur = []; prior = []
    for s in ALL:
        gs = g[g.season == s]
        mu, hfa, off, dfn = fit(gs, teams, lam)
        for t in teams: prior.append(dict(season=s, team=t, p_o=mu + off[t], p_d=mu + dfn[t], hfa_full=hfa))
        for d in sorted(gs.date.unique()):
            before = gs[gs.date < d]
            if len(before) < 60:  # too little data to fit: no adjustment (flag NaN -> Excel falls back to raw)
                for t in teams: cur.append(dict(season=s, date=d.strftime("%Y-%m-%d"), team=t, cur_o=np.nan, cur_d=np.nan))
                continue
            mu, hfa, off, dfn = fit(before, teams, lam)
            for t in teams: cur.append(dict(season=s, date=d.strftime("%Y-%m-%d"), team=t, cur_o=mu + off[t], cur_d=mu + dfn[t]))
    return pd.DataFrame(cur), pd.DataFrame(prior)


def audit(cur, lam, n=15):
    g = load(); teams = sorted(g[T].unique()); bad = 0
    for i in random.Random(3).sample(range(len(cur)), 4000):
        r = cur.iloc[i]
        if pd.isna(r.cur_o): continue
        n -= 1
        before = g[(g.season == r.season) & (g.date < pd.Timestamp(r.date))]
        assert before.date.max() < pd.Timestamp(r.date)
        mu, hfa, off, dfn = fit(before, teams, lam)
        bad += not (np.isclose(mu + off[r.team], r.cur_o) and np.isclose(mu + dfn[r.team], r.cur_d))
        if n == 0: break
    print("adj audit mismatches:", bad)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lam", type=float, default=5.0); ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    cur, prior = build(a.lam)
    out = ROOT / "data/backtest"; out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.lam:g}"
    cur.to_csv(out / f"adj_current_{tag}.csv", index=False); prior.to_csv(out / f"adj_prior_{tag}.csv", index=False)
    print("saved", len(cur), "current rows,", len(prior), "prior rows; lam", a.lam)
    if a.audit: audit(cur, a.lam)
