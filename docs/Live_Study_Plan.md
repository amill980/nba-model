# NBA live study plan: Phase A (explore) and Phase B (pre-registered test)

Status: **APPROVED by the user in chat, 2026-10-19** (decisions in section 5 recorded). Nothing here has been run on 2026-27 data. Success measure settled 2026-10-19 (section 5, item 2): closing-line value only.

## 0. Why this study
Historical tests (docs/Backtest_Findings.md, Confirmation_Results.md, Injury_v2_findings.md) show: the v1 ratings model does not beat the closing line; player availability is real information but the CLOSE already prices it (coefficient 0.04, 95% CI -1.1 to 1.3 on 3,663 games). The only remaining place an availability edge could live is **timing**: the interval after availability news is posted and before every book has moved. Past seasons cannot answer that (no injury-report timestamps, only open and close). 2026-27 can.

## 1. Data being collected (already running)
| Stream | How | Cadence |
|---|---|---|
| Injury reports | Official PDFs archived to `data/injuries/raw`, parsed to `data/injuries/injury_status.csv` | PDFs every 30 min (league posts every 15), parsed hourly |
| Odds | The Odds API, US books, spreads and totals, `data/odds/raw`, flattened to `odds_archive.csv` | up to 6 polls per game day (11:00, 13:30, 16:00, 18:30, 20:30, 22:00 ET), skipped if no game within 14 h |
| Results and box scores | nba_api, fetched after games | daily |
Budget: 2 credits per poll, about 324 credits a month, stop at 100 remaining. The same key is used by the CFB and WNBA workbooks.

Resolution limit: polls are 2 to 3 hours apart, so Phase A can say whether lines had absorbed a report by the next poll, not how many minutes it took.

## 2. Phase A: exploratory, 2026-10-20 to 2026-12-15
Looking at the data is allowed. Nothing in Phase A is a confirmation, and no betting claim comes out of it.

Questions:
1. **Coverage and health:** share of game days with all expected polls; share of games with a pre-tip injury report; parser failures; credit use. A daily health check script is built first.
2. **Material availability event:** a player whose typical minutes when playing (last 25 team games) are at least 20 is newly Out or Doubtful (or newly cleared) compared with the previous report for that game. Count events per week and by report time (day-before 5 pm vs game-day window).
3. **Line response:** for each event, the change in each book's spread/total from the last poll before the report to the first poll after, versus the size of the event in points (player value x minutes, from the v2 model).
4. **Book dispersion:** around events, how far the best and worst US book are from the consensus; which books lag.
5. **Stability of the v2 coefficient** with the true report instead of the box-score proxy (does the close still price availability fully?).

Output by 2026-12-15: a short Phase A report with counts and descriptive tables, plus the single Phase B hypothesis, frozen in writing.

Rules during Phase A: no bets are placed on the basis of these analyses; v1 stays frozen and is not tuned; any new idea is recorded with the date it was first seen.

## 3. Phase B: pre-registered confirmation, 2026-12-16 to end of regular season
Blinding: from 2026-12-16 only data collection runs. Analysis scripts take a cutoff date and are not run on Phase B data until the end (or a pre-set interim date, below).

Candidate hypothesis (to be finalised and signed by 2026-12-15, from Phase A):
> After a material availability event is posted, the best available US-book spread at the first poll after the report is better than the consensus closing spread, in the direction implied by the event, by an average of at least 0.5 points.

Draft design:
- Unit: one event-game; "paper bet" on the side favoured by the news at the best-priced of the books you can actually bet at (the user's book list is an input, see section 5).
- Primary metric: mean CLV in points versus the consensus close (mean of books at the last poll before tip).
- Test: permutation test (shuffle the direction of events within game day), one-sided, alpha 0.05, plus block bootstrap interval; pass also requires mean CLV >= 0.5.
- Sample size: if the CLV standard deviation per event is about 2 points, 80% power for 0.5 needs about 100 events; the number of eligible events is measured in Phase A, and if fewer than 100 are expected by season end, the test is declared underpowered up front and the end date moves.
- Interim look: none, except a data-health check (counts only, no CLV).
- Secondary (descriptive, no pass/fail): win rate versus breakeven at the price, flat 1-unit hypothetical profit and loss, by book, by report time, by event size.

## 4. Failure handling
- Decision 2026-10-20: the user will NOT change power settings, so the laptop sleeps and polls are missed (first miss: 2026-10-20 11:00, laptop asleep 08:13-12:09). The health check records every missed or late poll slot in `data/health/poll_gaps.csv`; that file is the exclusion record for Phase B. The odds, injury-archive, projections and daily-fetch tasks are set to wake the computer, which only helps on AC power (wake timers are off on battery). Retry-on-failure could not be set (Task Scheduler rejected the setting).
- If the odds task misses a day, it is recorded; days with missing polls are excluded by a rule written before looking (a game needs a poll at least once before and once after its report).
- If credits drop below 100, polling stops and the period is flagged.
- If the PDF layout changes, the parser fails loudly (rows whose team is not in the matchup, or zero rows from a non-empty file).

## 5. Decisions (recorded 2026-10-19)
1. **Books.** The user is in Georgia and can realistically use offshore books only (Bovada and similar), while wanting popular books such as DraftKings included. Therefore:
   - *Bettable set* (where paper bets are placed): bovada, betonlineag, mybookieag, betus, lowvig. Editable list; changing it after 2026-12-15 requires a dated amendment.
   - *Reference set* (consensus, benchmark, "who lags"): all books polled, including draftkings, fanduel, betmgm, espnbet, etc.
   - Current polling (`--regions us`) already includes every book above (verified against The Odds API's bookmaker list: all are in the `us` region).
   - Offshore-specific caveats to carry into any result: different juice (e.g. -105/-115 variants, LowVig lower), per-book limits, no regulator, and withdrawal/settlement risk. Offshore books often copy legal-book lines after a delay, which is exactly what Phase A will measure.
2. **Success measure (decided 2026-10-19): closing-line value (CLV) only.**
   - The Phase B pass/fail rests on mean CLV versus the consensus close (>= 0.5 points and permutation p < 0.05), nothing else.
   - Hypothetical profit and loss may be shown as a labeled descriptive extra, using a fixed flat stake of 1 unit at the actual price of the book used. It carries no pass/fail weight and no staking rule.
   - Real staking rules are considered only after CLV passes, and would be pre-registered separately.
   - Rationale: CLV needs about 100 events to reach a clear answer, whereas win rate or profit would need roughly 2,000 or more bets to prove a 2% edge, and it is not distorted by luck. Limits: CLV is a proxy, not profit, and does not capture offshore juice, account limits or settlement risk.
3. **Odds API upgrade:** deferred until Phase A shows whether a real lag exists.
4. **Plan approval:** approved.

## Addendum 2026-10-24: definition of the closing line
The Odds API returns in-play lines for games already started, which contaminated one daily report (a 27.5-point mid-game spread shown as a market line). From now on: odds rows are flagged `pregame`; the consensus close is the last pregame snapshot before tip; a game counts toward Phase B only if that snapshot is within 20 minutes of tip (`data/odds/closing_lines.csv`). A near-tip polling task (every 5 minutes, only polls when a game tips within 10 minutes and no snapshot covers it) replaces the 16:00, 18:30, 20:30 and 22:00 fixed polls. Games with a stale close are listed by the health check and excluded.

## Addendum 2026-11-23: where the model's team data comes from, the ESPN lines on the website, and the credit shortfall
Recorded before the change takes effect. The v1 model, its parameters, the flag threshold, the bettable and reference sets, the closing-line definition and the Phase B hypothesis are all unchanged. Nothing below is tuned on results.

1. **Team game logs for the model (data source change).** The daily projections are moving from the PC to a GitHub Actions job (`.github/workflows/nba-daily.yml`). stats.nba.com (nba_api) does not answer requests from GitHub's servers (tested 2026-11-16), so for 2026-27 the job reads team box scores from ESPN's public API (`scripts/fetch_games_espn.py`) and writes them in nba_api's layout. The job uses games through yesterday, as the PC's 06:30 fetch did. Validation, ESPN against nba_api over all 394 team-games from 2026-10-20 to 2026-11-15: no game missing on either side, and every figure the ratings read identical except two Charlotte turnovers (off by one), one home/away label for a neutral-site game, and one nba_api error (Denver credited with 168 minutes on 2026-11-14 instead of 240, which had raised Denver's pace about 2% and its model totals about 2.4 points). Replaying 2026-11-15 end to end: model margins differ by at most 0.16 points and totals by at most 0.1, except Denver's. Effective from the first report the cloud job publishes (date to be added when it goes live). The PC keeps its nba_api file for the player and roster data.
2. **What does not move.** The study's own collectors stay on the PC and are untouched: near-tip odds polling, `closing_lines.csv`, the injury-report archive, the health check. The consensus, the close and the CLV all come from The Odds API polls as before.
3. **ESPN lines on the website only.** When The Odds API gave no lines for a day (no credits left), the website's report for that day uses ESPN's own current line (usually one book) next to the model, written by `scripts/espn_fallback_report.py` with `source: espn_fallback` and `n_books` set to the number of ESPN providers. It writes nothing for a date that has a projections report in `docs/daily`, never replaces a report that has market lines, shows no leans, and does not read or write the odds archive, any snapshot file or `closing_lines.csv`. These lines are display only: they are not used for consensus, closing lines, CLV or any Phase A or Phase B figure.
4. **Credits (rule in section 4 applies).** The Odds API key had 78 credits left after the last poll, at 2026-11-22 01:01 UTC, which is below the 100-credit reserve, so polling stopped there and the days from 2026-11-22 are flagged. The credit counter resets on 2026-12-01. A game counts toward Phase B only if its own close is within 20 minutes of tip, so games on days without polling are excluded by the existing rule. Whether to buy more credits before 2026-12-16 is open: it is a data-collection decision, not a change to the plan, and will be recorded here when made.
