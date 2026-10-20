# Pre-registration (DRAFT, not signed): NBA confirmation test on 2025-26

Status: **SIGNED (approved by the user in chat, 2026-10-19), as drafted, before any 2025-26 outcome was viewed.** (Previously: DRAFT.) Nothing in this document has been run on 2025-26. The 2025-26 point-in-time table (`prep_backtest.py --include-confirmation`) has NOT been built. Date drafted: 2026-10-19.

## 1. Question
Does the frozen v1 model's disagreement with the OPENING line predict favourable closing-line movement (CLV) out of sample, on a season it was never tuned on?
Secondary: does it win against the opening line at better than the breakeven rate?

## 2. What is frozen (no change allowed after signing)
- Model: raw (not opponent-adjusted) blended ratings, `NBA_Model.xlsx` formulas as of the signing date. Opponent adjustment was tested and gave no gain (RMSE 14.113 vs 14.122); it is NOT part of the model.
- Parameters (tuned on 2023-24 and 2024-25 only, by margin RMSE): K = 10, home-court 1.94, rest 1.35 per day (cap 3), 3-in-4 penalty -0.59, margin SD 14.1.
- Edge definitions: spread edge = projected home margin + OPEN home spread; total edge = projected total - OPEN total. Bet the side of the edge. Ratings use only games dated strictly before the game date.
- Primary thresholds, fixed now: |edge| >= 3 points for spreads and for totals.

## 3. Data and population
- Games: all 2025-26 regular-season games (1,230), minus any game missing an ESPN open or close (count reported).
- Lines: ESPN core API open and close, reference book = ESPN BET where available, else DraftKings (ESPN BET covers Oct-Nov 2025, DraftKings after). The book switch is disclosed and a book-split result is reported.
- Not used: file A for 2025-26 (failed provenance gate).

## 4. Primary tests (two, Holm-corrected across them)
- T1 spreads and T2 totals: mean CLV in points of bets with |edge| >= 3, where CLV = movement of the line from open to close in the direction of the bet.
- Statistic and p-value: permutation test. Within each game day, randomly permute the model edges across that day's games (10,000 times), recompute mean CLV at the same threshold, and take the one-sided p-value. A block bootstrap by game day gives the confidence interval.
- Pass for each test: mean CLV >= +0.5 points AND Holm-adjusted one-sided p < 0.05.

## 5. Secondary (reported, no pass/fail)
- Win rate at the open line for the same bets, vs the 52.38% breakeven at -110 (z-test, Wilson interval).
- Win rate vs the close line (expected near or below 50%).
- Results by book (ESPN BET vs DraftKings), by month, and by games played (first 10 games vs later).
- Correlation of open edge with line movement, with bootstrap interval.

## 6. Known limitations (must be stated with any result)
- ESPN's open time is not recorded, so I cannot show the open was available before my ratings' information cutoff or bettable at size.
- One book per game; the book changes mid-season.
- In discovery the CLV pattern was strongest early in the season (correlation 0.58 in a team's first 10 games, 0.16 after 30), consistent with stale openers. If confirmation shows the same, that is not evidence of a durable edge against the close.
- Positive CLV against the open is not profit: the model did not beat the closing line on win rate in discovery.

## 7. Procedure and exposure
- After signing, the confirmation table is built once and each test is run once. No parameter, threshold or definition changes afterwards; any deviation is a dated amendment.
- The 2025-26 results are not viewed before signing. Exposure so far: accuracy and line-source checks on 2025-26 scores and lines (provenance gate only), no model outcomes.
- The live 2026-27 test (separate pre-registration) starts only after the model freeze.

Signature / date: approved by the user in chat, 2026-10-19 (signed text copied here by Claude).
