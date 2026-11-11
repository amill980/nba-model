@echo off
rem Wake-up catch-up poll: runs 2 min after the laptop resumes. Skips before 11:00 ET, if a snapshot is under 4 h old, or if no game is within 14 h.
cd /d "C:\Users\andre\projects\NBA model"
"C:\Users\andre\projects\NBA model\.venv\Scripts\python.exe" "C:\Users\andre\projects\NBA model\scripts\archive_odds.py" --regions us --markets spreads,totals --only-if-games --not-before-hour 11 --min-interval-min 240 --reserve 100 --then-report >> "C:\Users\andre\projects\NBA model\data\logs\odds_wake.log" 2>&1
