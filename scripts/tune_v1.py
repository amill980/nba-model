"""Tune rating parameters on DISCOVERY data by margin accuracy (RMSE), not by betting results.
2-fold check: fit on one season, score on the other. Prints a grid and the baseline (raw ratings)."""
import subprocess, sys, itertools
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
d0 = pd.read_csv(ROOT / "data/backtest/pit_games.csv")
d0["ps"] = d0.season.map({"2023-24": "2022-23", "2024-25": "2023-24"})
am = (d0.home_pts - d0.away_pts).values
def prep(lam):
    p = ROOT / f"data/backtest/adj_current_{lam:g}.csv"
    if not p.exists(): subprocess.run([sys.executable, str(ROOT / "scripts/opp_adjust.py"), "--lam", str(lam)], check=True, capture_output=True)
    cur = pd.read_csv(p); pri = pd.read_csv(ROOT / f"data/backtest/adj_prior_{lam:g}.csv")
    d = d0.copy()
    for side, tcol in (("h", "home"), ("a", "away")):
        c = cur.rename(columns={"team": tcol, "cur_o": f"{side}_cur_o", "cur_d": f"{side}_cur_d"})
        d = d.merge(c[["season", "date", tcol, f"{side}_cur_o", f"{side}_cur_d"]], on=["season", "date", tcol], how="left")
        q = pri.rename(columns={"season": "ps", "team": tcol, "p_o": f"{side}_pad_o", "p_d": f"{side}_pad_d"})
        d = d.merge(q[["ps", tcol, f"{side}_pad_o", f"{side}_pad_d"]], on=["ps", tcol], how="left")
    return d
def margins(d, K, adj=True):
    out = {}
    for s in ("h", "a"):
        gp = d[f"{s}_gp"]
        if adj:
            co = d[f"{s}_cur_o"].fillna(d[f"{s}_pad_o"]); cd = d[f"{s}_cur_d"].fillna(d[f"{s}_pad_d"])
            po, pdv = d[f"{s}_pad_o"], d[f"{s}_pad_d"]
        else:
            co = np.where(gp == 0, 0, 100 * d[f"{s}_cum_pts"] / d[f"{s}_cum_poss"].replace(0, np.nan).fillna(1))
            cd = np.where(gp == 0, 0, 100 * d[f"{s}_cum_opp"] / d[f"{s}_cum_poss"].replace(0, np.nan).fillna(1))
            po, pdv = d[f"{s}_prior_o"], d[f"{s}_prior_d"]
        out[s + "o"] = (K * po + gp * co) / (K + gp); out[s + "d"] = (K * pdv + gp * cd) / (K + gp)
        out[s + "p"] = (K * d[f"{s}_prior_pace"] + gp * d[f"{s}_avg_pace"]) / (K + gp)
    pace = (out["hp"] + out["ap"]) / 2
    H = pace * (out["ho"] + out["ad"] - d.lg_ortg) / 100; A = pace * (out["ao"] + out["hd"] - d.lg_ortg) / 100
    return (H - A).values, (H + A).values
def design(d):  # HCA, rest, fatigue regressors
    return np.column_stack([np.ones(len(d)), np.clip(d.h_rest - d.a_rest, -3, 3), d.h_g3in4 - d.a_g3in4])
rows = []
def evaluate(label, adj, lam, K):
    d = prep(lam) if adj else d0
    base, _ = margins(d, K, adj); X = design(d); tr = {}
    res = {}
    for train, test in (("2023-24", "2024-25"), ("2024-25", "2023-24")):
        mt = (d.season == train).values; me = (d.season == test).values
        beta = np.linalg.lstsq(X[mt], (am - base)[mt], rcond=None)[0]
        pred = base + X @ beta
        res[test] = (np.sqrt(np.mean((pred[me] - am[me]) ** 2)), np.mean(np.abs(pred[me] - am[me])), beta)
    rows.append(dict(label=label, lam=lam, K=K, rmse_oos=np.mean([res[k][0] for k in res]), mae_oos=np.mean([res[k][1] for k in res]),
                     hca=np.mean([res[k][2][0] for k in res]), rest=np.mean([res[k][2][1] for k in res]), fat=np.mean([res[k][2][2] for k in res])))
for K in (1, 2, 3, 5, 10, 20): evaluate("raw", False, 0, K)
for lam, K in itertools.product((2, 5, 10), (1, 2, 3, 4, 5, 7, 10)): evaluate("adj", True, lam, K)
r = pd.DataFrame(rows).sort_values("rmse_oos"); pd.set_option("display.width", 200)
print(r.round(3).head(12).to_string(index=False)); print("\nbest raw:"); print(r[r.label == "raw"].round(3).head(2).to_string(index=False))
r.to_csv(ROOT / "data/backtest/tune_v1_grid.csv", index=False)
