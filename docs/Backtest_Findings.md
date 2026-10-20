# Backtest findings, v0 model on discovery seasons (2023-24, 2024-25), 2026-10-19

**Status: exploratory, discovery data only, placeholder parameters (K=20, HCA=2.0, rest 1.0/day, 3-in-4 -1.5). No tuning yet. Not a confirmation. The 2025-26 season has not been touched.**

Data: 2,439 games. Lines = ESPN's stored open and close from ESPN BET (4 games DraftKings), verified against file A at 99.7-100% for the closing line. Ratings are point-in-time (200-game brute-force audit: 0 mismatches). Excel formulas reproduce an independent Python mirror exactly.

## Accuracy
| | Model | Market close | Market open |
|---|---|---|---|
| Spread MAE (pts) | 11.05 | 10.52 | 10.78 |
| Total MAE (pts) | 15.13 | 14.18 | 14.66 |

The model is less accurate than both the opening and closing lines, as expected for an unadjusted first version.

## Graded against the CLOSE (the pre-registered main test)
Spread win rate is 49.6-50.8% for edges up to 4 pts and falls to 47.6% (>=5 pts) and 40.6% (>=8 pts, n=106): large disagreements with the close are mostly the model being wrong. Totals sit at 49.9-52.1%. Nothing beats the 52.38% breakeven.

## Bet at the OPEN, with closing-line value (CLV)
Bets graded at the opening line and CLV measured against the close:
- Spread: win rate 50.5-52.0% for edges 1-5, 56.3% at >=8 (n=112). Average CLV rises steadily with edge: +0.56 pts (all games), +1.18 (>=3), +1.98 (>=5), +4.38 (>=8).
- Total: win rate 51.6% (all) to 56.4% (>=8, n=541, one-sided p=0.03 uncorrected). CLV +0.84 to +2.47.

## How to read this
- The monotone rise of CLV with edge is the interesting pattern: the model's disagreement with the OPEN predicts where the line later moves. Possible reasons: opening numbers are slow to reflect current-season form, or the model shares information with whatever moves lines.
- Not established: whether opening lines can actually be bet at those numbers and sizes; when ESPN BET's "open" was posted relative to our ratings' information cutoff (opening times are unknown); one book only; four tables x 11 thresholds were viewed, so scattered p-values need correction; the model was not tuned, so this is a baseline.
- Do not conclude there is a betting edge. The measurable next questions are: is the CLV relationship stable across both seasons and across opening-time buckets, and does it survive opponent adjustment and tuned parameters?

## Update after robustness checks and tuning (2026-10-19)
- The pattern holds in each season: correlation between edge-vs-open and line movement is 0.32 (2023-24) and 0.42 (2024-25) for spreads, 0.31 and 0.34 for totals; block-bootstrap 95% CI by game day [0.29, 0.45] spreads, [0.27, 0.37] totals.
- It is concentrated early in a team's season: 0.58 with fewer than 10 games played, 0.34 after 10, 0.16 after 30 (spreads). That fits stale opening lines rather than a persistent edge.
- Opponent-adjusted ratings (ridge, point-in-time, leak-audited) gave no real gain: out-of-sample RMSE 14.113 vs 14.122 raw. Not adopted. Scripts kept (`opp_adjust.py`, `tune_v1.py`).
- Prior-season ratings are a weak prior (year-over-year team-strength correlation 0.25-0.60), so the best shrinkage K is small (3-10); K=10 adopted for the workbook.
- Tuned (2-fold, margin RMSE, discovery only): K=10, HCA 1.94, rest 1.35/day, 3-in-4 -0.59, SD 14.1. Model MAE 11.02 vs market close 10.53 (RMSE 14.10 vs 13.56): still less accurate than the market.
- With tuned parameters: vs close, spreads 49.9% overall and 47.9% at edge >= 5, totals 49.5%; at the open, spread CLV +0.61 overall to +2.09 at >= 5, totals +0.95 to +2.95 at >= 8 (win rate at open up to 57%).
- Confirmation test drafted: `docs/preregistration_confirmation_clv.md` (unsigned).
