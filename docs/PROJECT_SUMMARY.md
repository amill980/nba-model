# NBA Model: Project Summary

**Last updated:** 2026-10-19. Narrative guide to what was built, what was found, and what is running. Authoritative detail lives in the other files in `docs/` and in `data/gates/`.

## 1. What this project is
An NBA betting model built Excel-first (`NBA_Model.xlsx`, rebuilt by `scripts/build_workbook.py`), following the CFB and WNBA workbooks and the CFB project's discipline: pre-register before looking, treat every claim as guilty until proven innocent, accept honest nulls. Python scripts prepare data and run the heavy point-in-time work; the model arithmetic a person would audit lives in Excel formulas.

## 2. What was found (in order)
1. **Data.** Four seasons of team and player game logs (nba_api), every regular-season score matched to ESPN (4,920 of 4,920). Gate records: `data/gates/`.
2. **Lines.** Kaggle file A equals ESPN BET's closing line in 2023-24 (99.7%) and 2024-25 (100%), but not 2025-26 (58-61%), so it was dropped. ESPN's public odds API stores open and close per book and became the line source (`scripts/fetch_espn_odds.py`). The "no whole-number lines" oddity is because ESPN BET posts half-points only.
3. **v1 ratings model** (blended prior/current ORtg, DRtg, pace; home court, rest, 3-in-4). Tuned on 2023-24 and 2024-25 only. It is less accurate than the market (spread MAE 11.0 vs 10.5). Against the closing line it wins about 50%.
4. **Closing-line value in discovery** looked promising (model disagreement with the OPEN predicted line movement, strongest early in a team's season).
5. **Signed confirmation on 2025-26 (run once): FAILED.** Spread CLV +0.35 pts (bar was +0.5; p = 0.001, so real but small); totals +0.03 (p = 0.25). Opponent adjustment was tested and gave no gain. See `Confirmation_Results.md`.
6. **Availability (injury) information is priced by the close.** Coefficient 0.04, 95% CI [-1.1, 1.3] on 3,663 games, though it does explain open-to-close movement. Any edge would have to be timing. See `Injury_v2_findings.md`.
7. **Live study** (`Live_Study_Plan.md`): Phase A (explore) to 2026-12-15, Phase B (pre-registered, closing-line value only, from 2026-12-16).

## 3. Layout
```
NBA_Model.xlsx           research workbook (no macros); README tab explains each tab
scripts\                 fetch_*.py (data), prep_backtest.py / opp_adjust.py / tune_v1.py (backtest),
                         run_confirmation.py (run once; lock file), injury_v2.py / eval_injury_v2.py,
                         archive_odds.py / archive_injuries.py / load_odds_archive.py / parse_injuries.py (live collection),
                         phase_a.py (exploration; refuses cutoff after 2026-12-15), health_check.py, daily_fetch.py, build_workbook.py
tests\                   synthetic checks for Phase A
docs\                    spec, findings, pre-registrations, results, live plan, this file
data\                    gitignored: raw feeds, archives, logs, health reports (gates and confirmation results are tracked)
.venv\                   project Python environment (required by scheduled tasks)
```

## 4. What is running (Windows Task Scheduler, computer must be on and logged in)
| Task | When | Does |
|---|---|---|
| NBA Odds Archive | 11:00, 13:30, 16:00, 18:30, 20:30, 22:00 ET | spreads+totals, US books, only if a game is within 14 h (2 credits/call) |
| NBA Injury Archive | every 30 min | saves new official injury report PDFs |
| NBA Injury Parse | hourly | PDFs to `data/injuries/injury_status.csv` |
| NBA Daily Fetch | 06:30 | refresh 2026-27 results, flatten odds, parse injuries |
| NBA Health Check | 23:30 | counts only, writes `data/health/health_<date>.txt` |
Logs: `data/logs/`. Python must be `.venv\Scripts\python.exe` (system packages are not visible to the scheduler).

## 5. Lessons learned (non-obvious)
- **Verify a data source against an independent one at full scale.** File A looked like closing lines; only the ESPN comparison showed it was one book, and wrong for one season.
- **A claim about verification must be checked for feasibility.** I proposed checking old datasets against our live archive; they do not overlap in time. The fix was a different independent source.
- **Positive CLV against the open is not an edge.** It faded out of sample, and the model never beat the close on win rate.
- **Efficient-close test beats a backtest of "does it add information".** The availability adjustment adds information (a, c) yet is fully priced (b).
- **Scheduled jobs fail silently unless watched.** The health check caught two tasks failing because the sandbox's packages were invisible to the scheduler; a project venv fixed it.
- **Hard guards beat promises.** `run_confirmation.py` has a lock file; `phase_a.py` refuses Phase B dates.

## 6. Data sources
nba_api (team/player logs), ESPN scoreboard and core odds APIs (scores, per-book open/close), The Odds API (live multi-book odds; free tier, shared key), official NBA injury report PDFs (from 2026-10-19 on; earlier PDFs are not retrievable), Kaggle files (provenance cross-check only).

## 7. Open items
- Phase A: first live data arrives 2026-10-20; read the health reports first.
- Freeze the single Phase B hypothesis and sign its pre-registration by 2026-12-15.
- Odds API upgrade ($30/month for 20,000 credits) only if Phase A shows a real lag.
- The Odds API key is in plain text in the CFB and WNBA workbooks and was pasted in chat: rotation advised.
- No moneyline backtest has been run (data is in the Lines tab).
