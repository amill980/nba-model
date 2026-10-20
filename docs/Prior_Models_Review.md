# What the CFB and WNBA models teach the NBA build (review notes, 2026-10-19)

Read: CFB_Model_v5.xlsm (a read-only temp copy; the original was locked), WNBA Model.xlsm, PROJECT_SUMMARY.md, Shared_Package_Extraction_Plan.docx, Shared_Package_Module_Inventory.xlsx.

## Workbook pattern to reuse (both workbooks)
Assumptions -> Team Ratings -> Game Projections / weekly tabs -> All Games -> Bet Record + Bet Log (Locked) -> Backtest -> Edge Significance, with Odds Archive and Ratings Archive as point-in-time stores.
- Rating blend: (K x prior + GP x current) / (K + GP). K = 10 (WNBA, 40 games), 3 (CFB, ~13 games, with a note that a naive scale-down was wrong). NBA K must be tuned in the backtest, not scaled by hand.
- Projection: efficiency x pace, plus team-specific HCA (fallback to league average until a minimum home/away sample), rest differential (coefficient 1 pt/day, cap 3 days), 3-in-4 penalty (-1.5), recent-form and injury adjustments as manual inputs.
- Decision: |edge| >= 1.5 pts; stake tiers 1.5/3/5/8 pts -> $10/15/25/35.
- Vig-free fair probability uses the multiplicative method (Game Projections section 5). Good starting point for moneylines; check the power/Shin method on lopsided prices.
- CFB "Refresh Strategy" tab: queries are tiered by how often their data changes (never / weekly / every refresh). Historical pulls are never repeated. Do the same for NBA.

## Cautions
- **Scale:** CFB logs reach 22,000 rows and use AVERAGEIFS/COUNTIFS across them; the workbook is 12 MB with a 43,000-row Odds Archive. NBA (about 2,500 team-games a season, three seasons of backtest) will be slower still. Supports the hybrid plan: script builds history tables, Excel holds logic.
- **Flat threshold sweep:** the CFB Edge Threshold Analysis shows spread win rate about 49-50% at every threshold from 1.5 to 7 points. A real signal should improve as the required edge grows. Build the NBA sweep early and treat a flat curve as evidence of no edge.
- **Shared Odds API key:** the same key is typed into the Assumptions sheets of the CFB and WNBA workbooks, and the NBA archive uses it too. All three draw on one 500-credit monthly allowance, so CFB "Odds (Live)" refreshes reduce what the NBA archive can spend. The CFB workbook also holds a plain-text CFBD key. Rotating the Odds key means updating both workbooks.

## Shared-package extraction plan (status: plan only, nothing moved)
- Tier A (move as-is): extra_books, guarded_io, metrics, client. Tier B (generalize first): snapshot, odds_api, odds_match, formatting, refresh_runner, significance, thresholds, schedule, paths.
- The shared package does not exist, so the NBA model should not wait for it. The NBA data scripts already follow its patterns (key only from the environment, redacted URLs, raw snapshots with provenance, quota log, credit reserve).
- Gaps the plan names that the NBA needs: per-price breakeven (metrics.py assumes -110), moneyline market handling and price-based Best Book, and a per-key (not per-sport) credit budget.
- Decision still open: where the shared package lives, and whether the NBA repo adopts it once it exists.
