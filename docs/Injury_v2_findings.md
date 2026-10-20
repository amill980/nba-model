# v2 development: player availability (2026-10-19)

Scripts: `fetch_players.py`, `injury_v2.py`, `eval_injury_v2.py`. All three seasons 2023-24..2025-26 are DEVELOPMENT data for v2; v2 is confirmed on live 2026-27 only.

## Method (development proxy)
- Player values: ridge regression refit monthly using only earlier games (game rows, x = +/- minutes/48, y = home margin).
- Game adjustment = (home players who appeared, at their typical minutes) minus (home recent-norm roster) minus the same for the away team, in points of margin.
- Availability proxy = who actually appeared. This approximates the pre-game report but includes late scratches (optimistic). The live version must use the official injury report. Official past-season report PDFs are NOT retrievable (only roughly Jan 2026 onward returns 200; earlier dates return 403), so our own archive is the history from now on.

## Results (3,663 games; ridge lambda 800, 25-game window; lambda not yet tuned)
| Question | Coefficient on the adjustment | 95% CI | Reading |
|---|---|---|---|
| (a) Actual margin minus v1 margin | 4.2 (by season 5.2, 3.0, 4.8) | [2.9, 5.6] | Adds information. Coefficient well above 1 means lambda shrinks player values too much. RMSE only 14.289 -> 14.215. |
| (b) Actual margin vs the CLOSING line | 0.04 (by season 1.0, -1.3, 0.7) | [-1.1, 1.3] | **The close already prices availability.** No edge against the close from this information. |
| (c) Open-to-close line movement | 1.44 (1.7, 1.3, 1.5) | [1.1, 1.8] | Availability explains how lines move after they open. |

## Conclusion
Availability information is real (a, c) but fully priced by the close (b). A betting edge from it can only come from timing: acting after news posts and before every book has moved. Our data (open, close, 4 snapshots a day) cannot test that. It needs frequent line snapshots around injury report postings during 2026-27.

## Live study design (proposed)
- Phase A, exploratory (about 2026-10-20 to 2026-12-15): archive injury reports (15-minute PDFs, parser to be built) and poll odds densely on game days. Questions: how long after a material status change do lines move, which books lag, how large is the stale-price gap.
- Phase B, pre-registered confirmation (from 2026-12-16): frozen rule, frozen thresholds, one test.
- Cost: The Odds API gives 500 free credits a month and 20,000 for $30/month. One call for spreads only in one region costs 1 credit; 3 markets cost 3. Hourly polling, 11:00-23:00 ET, spreads+totals+moneyline in the US region is about 36 credits/day (1,080/month), which exceeds the free tier.
