"""v2 development: player availability adjustment, point-in-time.

Availability proxy (development only): who actually appeared in the game. This approximates the final
pre-game report (most absences are announced) but includes late scratches, so it is optimistic. The LIVE
version must use the official injury report instead.

1. Player values: ridge regression refit at the start of each calendar month using ONLY earlier games
   (all seasons back to 2022-23). Row = game; x[p] = +minutes/48 for home players, -minutes/48 for away;
   y = home margin; intercept = home-court. v[p] = points of margin per 48 minutes (vs average).
2. Team adjustment for a game: S_today - S_avg where
   S_today = sum over players who appeared of v[p] * e[p]/48, e[p] = mean minutes when playing in the team's last N games
   S_avg   = sum over players in those N games of v[p] * (their mean minutes incl. games missed)/48.
   Positive = healthier than the recent norm. Game adjustment = home adj - away adj.
Usage: python scripts/injury_v2.py [--lam 800] [--n 25]  -> data/backtest/injury_adj_<lam>_<n>.csv
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SEAS = ["2022-23", "2023-24", "2024-25", "2025-26"]


def load():
    fr = []
    for s in SEAS:
        p = pd.read_csv(ROOT / "data/players" / f"player_games_{s}.csv"); p["season"] = s; fr.append(p)
    p = pd.concat(fr, ignore_index=True)
    p["date"] = pd.to_datetime(p.GAME_DATE); p["min"] = p.MIN.astype(float)
    t = pd.concat([pd.read_csv(ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv") for s in SEAS], ignore_index=True)
    t["home"] = ~t.MATCHUP.str.contains("@")
    games = t.groupby("GAME_ID").apply(lambda g: pd.Series({
        "date": pd.Timestamp(g.GAME_DATE.iloc[0]), "home": g[g.home].TEAM_ABBREVIATION.iloc[0] if g.home.sum() == 1 else None,
        "away": g[~g.home].TEAM_ABBREVIATION.iloc[0] if g.home.sum() == 1 else None,
        "margin": (g[g.home].PTS.iloc[0] - g[~g.home].PTS.iloc[0]) if g.home.sum() == 1 else np.nan}), include_groups=False).reset_index()
    games = games.dropna(subset=["home"]).sort_values("date").reset_index(drop=True)
    return p, games


def fit_values(p, games, cutoff, lam):
    g = games[games.date < cutoff]
    pl = p[p.GAME_ID.isin(g.GAME_ID)]
    pids = sorted(pl.PLAYER_ID.unique()); pi = {x: i for i, x in enumerate(pids)}; gi = {x: i for i, x in enumerate(g.GAME_ID)}
    X = np.zeros((len(g), len(pids) + 1)); X[:, -1] = 1.0
    home_of = dict(zip(g.GAME_ID, g.home))
    for r in pl.itertuples(index=False):
        sign = 1.0 if r.TEAM_ABBREVIATION == home_of[r.GAME_ID] else -1.0
        X[gi[r.GAME_ID], pi[r.PLAYER_ID]] += sign * r.min / 48.0
    y = g.margin.values
    P = np.eye(X.shape[1]) * lam; P[-1, -1] = 0
    beta = np.linalg.solve(X.T @ X + P, X.T @ y)
    return dict(zip(pids, beta[:-1])), beta[-1]


def adjustments(p, games, lam, N):
    start = pd.Timestamp("2023-10-01")
    months = sorted({pd.Timestamp(d.year, d.month, 1) for d in games[games.date >= start].date})
    vals = {m: fit_values(p, games, m, lam)[0] for m in months}
    rows = []
    pt = p.sort_values(["TEAM_ABBREVIATION", "date"])
    for gm in games[games.date >= start].itertuples(index=False):
        v = vals[pd.Timestamp(gm.date.year, gm.date.month, 1)]
        out = {"GAME_ID": gm.GAME_ID}
        for side, team in (("h", gm.home), ("a", gm.away)):
            # team's previous N games (same season) strictly before this date
            tg = games[((games.home == team) | (games.away == team)) & (games.date < gm.date)]
            tg = tg[tg.date >= gm.date - pd.Timedelta(days=200)].tail(N)
            if len(tg) < 5: out[side + "_adj"] = 0.0; continue
            pp = p[(p.TEAM_ABBREVIATION == team) & p.GAME_ID.isin(tg.GAME_ID)]
            n = len(tg)
            agg = pp.groupby("PLAYER_ID")["min"].agg(["sum", "count"])
            avg_all = agg["sum"] / n                      # minutes per game incl. games missed
            when = (agg["sum"] / agg["count"]).where(agg["count"] >= 3, 0.0)  # minutes when playing
            s_avg = sum(v.get(pid, 0.0) * m / 48 for pid, m in avg_all.items())
            today = p[(p.GAME_ID == gm.GAME_ID) & (p.TEAM_ABBREVIATION == team)].PLAYER_ID
            s_today = sum(v.get(pid, 0.0) * when.get(pid, 0.0) / 48 for pid in today)
            out[side + "_adj"] = s_today - s_avg
        rows.append(out)
    df = pd.DataFrame(rows); df["adj"] = df.h_adj - df.a_adj
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lam", type=float, default=800); ap.add_argument("--n", type=int, default=25)
    a = ap.parse_args()
    p, games = load()
    df = adjustments(p, games, a.lam, a.n)
    df = games.merge(df, on="GAME_ID")
    out = ROOT / "data/backtest" / f"injury_adj_{a.lam:g}_{a.n}.csv"; df.to_csv(out, index=False)
    print("saved", out.name, len(df), "games; adj sd", round(df.adj.std(), 3), "mean", round(df.adj.mean(), 3))
