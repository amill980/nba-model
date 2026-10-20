"""Confirmation test on 2025-26, exactly as pre-registered (docs/preregistration_confirmation_clv.md).
RUN ONCE. A lock file blocks any re-run. Frozen parameters below; do not edit after signing.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "data/backtest/CONFIRMATION_RUN.lock"
if LOCK.exists():
    sys.exit("Confirmation test already run (lock file present). Further runs would violate the pre-registration.")

K, HCA, RC, CAP, FT = 10, 1.94, 1.35, 3, -0.59      # frozen
THR = 3.0                                             # frozen primary threshold
NPERM, NBOOT, SEED = 10000, 2000, 20261019
d = pd.read_csv(ROOT / "data/backtest/pit_confirmation.csv")
assert set(d.season) == {"2025-26"}

def bl(p, gp, cum, poss): return (K * p + gp * np.where(gp == 0, 0, 100 * cum / poss.replace(0, np.nan).fillna(1))) / (K + gp)
ho = bl(d.h_prior_o, d.h_gp, d.h_cum_pts, d.h_cum_poss); hd = bl(d.h_prior_d, d.h_gp, d.h_cum_opp, d.h_cum_poss)
ao = bl(d.a_prior_o, d.a_gp, d.a_cum_pts, d.a_cum_poss); ad = bl(d.a_prior_d, d.a_gp, d.a_cum_opp, d.a_cum_poss)
hp = (K * d.h_prior_pace + d.h_gp * d.h_avg_pace) / (K + d.h_gp); ap = (K * d.a_prior_pace + d.a_gp * d.a_avg_pace) / (K + d.a_gp)
pace = (hp + ap) / 2
H = pace * (ho + ad - d.lg_ortg) / 100; A = pace * (ao + hd - d.lg_ortg) / 100
d["margin"] = H - A + HCA + RC * np.clip(d.h_rest - d.a_rest, -CAP, CAP) + (d.h_g3in4 - d.a_g3in4) * FT
d["total"] = H + A
am = (d.home_pts - d.away_pts).values; at = (d.home_pts + d.away_pts).values
d["s_edge"] = d.margin + d.open_home_spread; d["t_edge"] = d.total - d.open_total
d["s_move"] = d.open_home_spread - d.mkt_home_spread        # + = moved toward home
d["t_move"] = d.mkt_total - d.open_total                     # + = moved up
rng = np.random.default_rng(SEED)
days = d.date.values; udays = np.unique(days); day_idx = [np.where(days == u)[0] for u in udays]

def clv(edge, move, thr):
    m = np.abs(edge) >= thr
    return np.where(edge > 0, 1, -1)[m] * move[m]

def mean_clv(edge, move, thr):
    c = clv(edge, move, thr); return c.mean() if len(c) else np.nan

def perm_p(edge, move, thr):
    obs = mean_clv(edge, move, thr); cnt = 0; valid = 0
    for _ in range(NPERM):
        e2 = edge.copy()
        for ix in day_idx: e2[ix] = rng.permutation(edge[ix])
        v = mean_clv(e2, move, thr)
        if not np.isnan(v): valid += 1; cnt += v >= obs
    return obs, (cnt + 1) / (valid + 1)

def boot_ci(edge, move, thr):
    vals = []
    for _ in range(NBOOT):
        pick = rng.choice(len(udays), len(udays)); ix = np.concatenate([day_idx[i] for i in pick])
        v = mean_clv(edge[ix], move[ix], thr)
        if not np.isnan(v): vals.append(v)
    return np.percentile(vals, [2.5, 97.5])

res = {"n_games": int(len(d)), "books": d.book.value_counts().to_dict()}
out = []
for name, e, mv in (("T1 spread", d.s_edge.values, d.s_move.values), ("T2 total", d.t_edge.values, d.t_move.values)):
    obs, p = perm_p(e, mv, THR); lo, hi = boot_ci(e, mv, THR)
    res[name] = dict(n_bets=int((np.abs(e) >= THR).sum()), mean_clv=float(obs), perm_p=float(p), ci95=[float(lo), float(hi)])
ps = sorted([(res[k]["perm_p"], k) for k in ("T1 spread", "T2 total")])
holm = {ps[0][1]: min(1, 2 * ps[0][0]), ps[1][1]: min(1, max(ps[1][0], min(1, 2 * ps[0][0])))}
for k in ("T1 spread", "T2 total"):
    r = res[k]; r["holm_p"] = float(holm[k]); r["PASS"] = bool(r["mean_clv"] >= 0.5 and r["holm_p"] < 0.05)

# secondary
sec = {}
BE = 110 / 210
def wl(edge, line_res):
    m = np.abs(edge) >= THR; side = edge[m] > 0; r = line_res[m]
    win = np.where(r == 0, np.nan, (r > 0) == side); w = np.nansum(win); n = np.sum(~np.isnan(win))
    return int(w), int(n)
s_open_res = am + d.open_home_spread.values; s_close_res = am + d.mkt_home_spread.values
t_open_res = at - d.open_total.values; t_close_res = at - d.mkt_total.values
for nm, e, ro, rc in (("spread", d.s_edge.values, s_open_res, s_close_res), ("total", d.t_edge.values, t_open_res, t_close_res)):
    w, n = wl(e, ro); w2, n2 = wl(e, rc)
    z = (w / n - BE) / np.sqrt(BE * (1 - BE) / n)
    sec[nm] = dict(open_win=f"{w}/{n} = {w/n:.4f}", open_z_vs_breakeven=float(z), close_win=f"{w2}/{n2} = {w2/n2:.4f}")
def split(mask_fn, label):
    for nm, e, mv in (("spread", d.s_edge.values, d.s_move.values), ("total", d.t_edge.values, d.t_move.values)):
        for key, m in mask_fn.items():
            c = clv(e[m], mv[m], THR); sec[f"{nm} CLV, {label}={key}"] = f"n={len(c)} mean={c.mean():.3f}" if len(c) else "n=0"
split({b: (d.book == b).values for b in d.book.unique()}, "book")
d["mon"] = d.date.str[:7]; split({m: (d.mon == m).values for m in sorted(d.mon.unique())}, "month")
gm = np.minimum(d.h_gp, d.a_gp).values
split({"<10 games": gm < 10, ">=10 games": gm >= 10, ">=30 games": gm >= 30}, "games played")
for nm, e, mv in (("spread", d.s_edge.values, d.s_move.values), ("total", d.t_edge.values, d.t_move.values)):
    sec[f"{nm} corr(open edge, line move)"] = float(np.corrcoef(e, mv)[0, 1])
sec["model MAE vs actual margin"] = float(np.mean(np.abs(d.margin.values - am)))
sec["market close MAE"] = float(np.mean(np.abs(-d.mkt_home_spread.values - am)))
sec["market open MAE"] = float(np.mean(np.abs(-d.open_home_spread.values - am)))
res["secondary"] = sec
(ROOT / "data/backtest/confirmation_results.json").write_text(json.dumps(res, indent=2))
LOCK.write_text("confirmation test run once; do not rerun")
print(json.dumps(res, indent=2))
