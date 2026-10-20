# NBA Betting Model: One-Page Spec (v0.1, 2026-10-19)

## 1. Question and success criteria
**Question:** Can a team-rating model find NBA spreads, totals or moneylines where its price beats the market by enough to overcome the vig, out of sample?

**Success is not "it wins."** It is:
1. A rigorous, point-in-time pipeline (pre-registration, look-ahead audit, data gates), as in the CFB project.
2. A pre-registered, honestly reported answer on whether an edge exists. "No edge" is a valid result.
3. Closing-line value (CLV) tracked from day one as the main short-run skill signal.

Expectation: the NBA is a sharp, heavily bet market. The default prior is no demonstrable edge.

## 2. Markets and breakeven math
| Market | Bet | Breakeven | Test |
|---|---|---|---|
| Spread | Side vs. line | 52.38% at -110; use the actual price | One-sided z-test vs. price-specific breakeven |
| Total | Over/Under | Same | Same |
| Moneyline | Side | No-vig implied probability of each bet, which differs by price | Model probability minus no-vig market probability; ROI and calibration |
| Player props | **Out of scope (parked)** | | |

Each market is its own pre-registered hypothesis. Results are never pooled across markets.
Model win probability for moneylines: projected margin through a normal curve (margin SD about 12 points, calibrated on history, not assumed).

## 3. Model v0 (baseline)
- Rating: opponent-adjusted net rating (ORtg - DRtg), blended with the prior season: (K x prior + games x current) / (K + games). K is tuned in the backtest; starting guess about 20 (WNBA used 10 for 40 games).
- Projection: matchup efficiency x pace, plus team-specific home court, plus rest differential, minus a 3-in-4 fatigue penalty.
- Injury input: **v0 manual** (WNBA-style). v1 replaces it with player-level impact x minutes.
- Decision: edge = model - market; bet only when |edge| clears a threshold (starting 1.5 pts, tuned on discovery data only). Stake tiers per the WNBA table.
- Excel structure: Assumptions, Team Stats, Power Ratings, Game Predictor, Odds + Odds Archive, Team Stats Archive, All Games, Bet Record + locked Bet Log, Backtest, Edge Significance, CLV.

## 4. Candidate factors (one pre-registered test each; optional joint test)
Rest and back-to-back; 3-in-4 / 4-in-6; travel and time zone; altitude; injuries and availability; recent form; 3-point and free-throw shooting regression; late-season motivation (tanking, clinched seeds); referee crew (totals).
Factors are specified before testing. Rejections are permanent and recorded.

## 5. Data sources and gates
| Need | Source | Gate before use |
|---|---|---|
| Schedule, results, box scores | `nba_api` / Basketball-Reference / ESPN | Full-season cross-check between two sources (scores, dates, home/away) |
| Injuries | Official NBA injury report (PDFs, 15-minute stamps, due 5 pm local day before; 11 am-1 pm game day) | Archive going forward; history needs a coverage check |
| Player impact | EPM / BPM / RAPM | Confirm point-in-time values exist, or exclude (end-of-season values are look-ahead) |
| Live odds | The Odds API `basketball_nba` (existing client) | Compare vs. a second source on matched games, thresholds written first |
| **Historical lines** | Odds API historical endpoint (paid plans; from 2020-06-06; 5-minute snapshots since Sep 2022; 10 credits per market per region) | **Hard gate:** at least 3 seasons with closing lines at known timestamps. Otherwise the backtest is blocked |
| Team-name map | Exact-match table (never substring) | 30 teams, zero ambiguity |

Cost note: a historical backfill is roughly 10 credits x markets x regions per snapshot. Estimate credits and confirm the plan before buying.

## 6. Validation design
- **Discovery:** 2 seasons (2023-24, 2024-25). **Confirmation:** 2025-26, tested once. **Live:** 2026-27 after model freeze.
- Look-ahead audit of every feature: "what was known at tip-off minus the injury-report time?"
- Power calculation first. Approximate: at ~1,000 bets and a true 54% win rate, one-sided power at p<0.05 is about 25-30%. Fewer bets means less. CLV and ROI are reported next to win rate with p-values.
- Multiple-comparison control (Benjamini-Hochberg) across the factor family, with the family size disclosed.

## 7. Live test (pre-registered)
- **Start now (no model needed):** archive daily NBA odds snapshots and injury reports. Lines can't be recovered later without paying for history.
- **Freeze:** after the backtest, freeze model, thresholds and population; sign the pre-registration; only games after the freeze date are blind.
- Games before the freeze are excluded from the blind test and disclosed as exposed.
- The scoring code is built only when the test is due, and nobody looks at blinded results early. A descriptive tracker (labeled "NOT A VERDICT") is allowed and disclosed.

## 8. Daily run (Excel)
1. Refresh Power Queries (odds, team stats, results, injuries).
2. Archive team stats (inputs).
3. Archive odds snapshot before each tip-off (and again near close for CLV).
4. Post-game: sync graded bets into the locked log.
Run as late as practical before tip-off, because injury news moves lines.

## 9. Open items
- Excel approach: hybrid (script builds history tables, Power Query loads them, logic in Excel) is assumed until confirmed.
- Historical-odds plan and credit budget.
- Player-impact source with point-in-time values.
- Read the CFB workbook, extraction plan and module inventory before building the Excel skeleton.
