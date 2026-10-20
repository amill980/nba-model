"""Daily refresh of current-season results (team and player game logs), then odds flatten and injury parse.
Runs fetch_games.py and fetch_players.py for the current season with --refresh, then the two loaders.
Usage: python scripts/daily_fetch.py [--season 2026-27]
"""
import argparse, subprocess, sys
from pathlib import Path
S = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument("--season", default="2026-27"); a = ap.parse_args()
steps = [["fetch_games.py", "--seasons", a.season, "--refresh"], ["fetch_players.py", "--seasons", a.season, "--refresh"],
         ["load_odds_archive.py"], ["parse_injuries.py"]]
rc = 0
for st in steps:
    r = subprocess.run([sys.executable, str(S / st[0])] + st[1:], capture_output=True, text=True)
    print(f"{st[0]}: exit {r.returncode}\n{(r.stdout or '').strip()[-300:]}\n{(r.stderr or '').strip()[-300:]}")
    rc = rc or r.returncode
sys.exit(rc)
