# Confirmation results: 2025-26 (pre-registered test, run once, 2026-10-19)

Pre-registration: `docs/preregistration_confirmation_clv.md` (signed 2026-10-19). Run with `scripts/run_confirmation.py` (lock file prevents re-runs). Raw output: `data/backtest/confirmation_results.json`. No parameter, threshold or definition was changed after signing.

Population: 1,224 games (ESPN BET 297, DraftKings 927). Frozen model: K=10, HCA 1.94, rest 1.35/day, 3-in-4 -0.59.

| Test | Bets (|edge| >= 3) | Mean CLV | 95% CI | Permutation p | Holm p | Pass? |
|---|---|---|---|---|---|---|
| T1 spreads | 485 | +0.35 pts | [0.16, 0.55] | 0.0006 | 0.0012 | **No** (below the +0.5 bar) |
| T2 totals | 706 | +0.03 pts | [-0.21, 0.25] | 0.25 | 0.25 | **No** |

**Verdict: both primary tests fail the pre-registered pass rule.**
- Spreads: the effect is statistically real (not chance) but much smaller than in discovery (+1.31 pts at the same threshold) and below the required +0.5.
- Totals: the discovery pattern did not replicate at all.
- Correlation of open edge with line movement fell from 0.39 (spreads) / 0.35 (totals) in discovery to 0.13 / 0.09.

Secondary (descriptive only): win rate at the open for the same bets was 48.3% (spreads, z = -1.82 vs breakeven) and 51.4% (totals, z = -0.51); against the close 49.5% and 49.4%. Model margin MAE 11.47 vs market close 10.89 and open 11.09: still less accurate than both.

Exploratory splits (not part of the pass rule; do not tune on them): spread CLV +0.73 (ESPN BET, n=128) vs +0.22 (DraftKings, n=357); +0.78 with fewer than 10 games played vs +0.14 after 30. Consistent with a weak early-season staleness effect that is smaller against DraftKings, but a book change and an early-season effect cannot be separated here.

Limitations unchanged from the pre-registration: ESPN's open time is unknown, one book per game, the book switches mid-season.

2025-26 is now exposed: any new model idea needs a new confirmation season (2026-27 live).
