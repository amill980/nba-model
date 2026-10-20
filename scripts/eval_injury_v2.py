"""Development evaluation of the availability adjustment (all three seasons are development data for v2;
the v2 confirmation is the live 2026-27 season). Reports, for adjustment series file given:
 (a) y1 = actual margin - v1 margin  ~  adj          (does it add information, coefficient near 1?)
 (b) y2 = actual margin + close home spread ~ adj     (does the CLOSE already price it? coef 0 = efficient)
 (c) y3 = close - open line move (toward home) ~ adj  (does it explain line movement?)
Block bootstrap by game day for the coefficient CI."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
K, HCA, RC, FT = 10, 1.94, 1.35, -0.59
def v1(d):
    def bl(p, gp, cum, poss): return (K * p + gp * np.where(gp == 0, 0, 100 * cum / poss.replace(0, np.nan).fillna(1))) / (K + gp)
    ho = bl(d.h_prior_o, d.h_gp, d.h_cum_pts, d.h_cum_poss); hd = bl(d.h_prior_d, d.h_gp, d.h_cum_opp, d.h_cum_poss)
    ao = bl(d.a_prior_o, d.a_gp, d.a_cum_pts, d.a_cum_poss); ad = bl(d.a_prior_d, d.a_gp, d.a_cum_opp, d.a_cum_poss)
    hp = (K * d.h_prior_pace + d.h_gp * d.h_avg_pace) / (K + d.h_gp); ap = (K * d.a_prior_pace + d.a_gp * d.a_avg_pace) / (K + d.a_gp)
    pace = (hp + ap) / 2
    H = pace * (ho + ad - d.lg_ortg) / 100; A = pace * (ao + hd - d.lg_ortg) / 100
    return H - A + HCA + RC * np.clip(d.h_rest - d.a_rest, -3, 3) + (d.h_g3in4 - d.a_g3in4) * FT
def ols(x, y):
    X = np.column_stack([np.ones(len(x)), x]); b = np.linalg.lstsq(X, y, rcond=None)[0]; return b[1]
def run(path):
    d = pd.concat([pd.read_csv(ROOT / "data/backtest/pit_games.csv"), pd.read_csv(ROOT / "data/backtest/pit_confirmation.csv")], ignore_index=True)
    a = pd.read_csv(path)[["GAME_ID", "adj"]].rename(columns={"GAME_ID": "game_id"})
    d["game_id"] = d.game_id.astype(str).str.zfill(10); a["game_id"] = a.game_id.astype(str).str.zfill(10)
    d = d.merge(a, on="game_id")
    d["base"] = v1(d); d["am"] = d.home_pts - d.away_pts
    y1 = d.am - d.base; y2 = d.am + d.mkt_home_spread; y3 = d.open_home_spread - d.mkt_home_spread
    days = d.date.values; ud = np.unique(days); idx = [np.where(days == u)[0] for u in ud]; rng = np.random.default_rng(5)
    print(f"{Path(path).name}: n={len(d)} adj sd={d.adj.std():.3f}  v1 RMSE={np.sqrt((y1**2).mean()):.3f}  RMSE after adding adj={np.sqrt(((y1 - ols(d.adj.values, y1.values) * d.adj)**2).mean()):.3f}")
    for lab, y in (("(a) actual - v1", y1), ("(b) actual vs CLOSE", y2), ("(c) open->close move", y3)):
        xs = d.adj.values; ys = y.values; b = ols(xs, ys); bs = []
        for _ in range(500):
            ix = np.concatenate([idx[i] for i in rng.choice(len(ud), len(ud))]); bs.append(ols(xs[ix], ys[ix]))
        lo, hi = np.percentile(bs, [2.5, 97.5])
        by = {s: round(ols(xs[(d.season == s).values], ys[(d.season == s).values]), 2) for s in d.season.unique()}
        print(f"   {lab:22s} coef={b:6.3f}  95% CI [{lo:6.3f},{hi:6.3f}]  by season {by}")
if __name__ == "__main__":
    for p in sys.argv[1:]: run(p)
