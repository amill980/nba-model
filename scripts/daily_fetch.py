"""Daily refresh of current-season results (team and player game logs), then odds flatten and injury parse.
Runs fetch_games.py and fetch_players.py for the current season with --refresh, then the two loaders.

stats.nba.com often times out or drops the connection, so each of the two network steps is tried up to three times, with a pause
between attempts. A second scheduled run with --if-stale tries again later in the day, but only if the player logs are still more
than a day behind.

Usage: python scripts/daily_fetch.py [--season 2026-27] [--if-stale]
"""
import argparse, csv, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

S = Path(__file__).resolve().parent
ROOT = S.parent
ATTEMPTS = 3
WAITS = (45, 120)          # seconds to wait after the first and second failed attempts


def run_with_retry(cmd, runner=subprocess.run, sleep=time.sleep, attempts=ATTEMPTS, waits=WAITS):
    """Run cmd until it exits 0 or the attempts are used. Returns (last result, attempts used)."""
    r = None
    for n in range(1, attempts + 1):
        r = runner(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return r, n
        if n < attempts:
            sleep(waits[min(n - 1, len(waits) - 1)])
    return r, attempts


def newest_player_game(season, root=ROOT):
    f = root / "data" / "players" / f"player_games_{season}.csv"
    if not f.exists():
        return None
    with f.open(newline="", encoding="utf-8") as h:
        dates = [row["GAME_DATE"] for row in csv.DictReader(h)]
    return max(dates) if dates else None


def is_stale(newest, now=None):
    """True if the newest player game on file is older than yesterday (Eastern time), or there is none."""
    if not newest:
        return True
    today = (now or datetime.now(ZoneInfo("America/New_York"))).date()
    return datetime.strptime(newest, "%Y-%m-%d").date() < today - timedelta(days=1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026-27")
    ap.add_argument("--if-stale", action="store_true", help="do nothing unless the player logs are more than a day behind")
    a = ap.parse_args(argv)
    if a.if_stale:
        newest = newest_player_game(a.season)
        if not is_stale(newest):
            print(f"skipped: player logs are current (newest game {newest})")
            return 0
        print(f"player logs are behind (newest game {newest}); fetching again")
    steps = [["fetch_games.py", "--seasons", a.season, "--refresh"], ["fetch_players.py", "--seasons", a.season, "--refresh"],
             ["load_odds_archive.py"], ["parse_injuries.py"]]
    network = {"fetch_games.py", "fetch_players.py"}
    rc = 0
    for st in steps:
        cmd = [sys.executable, str(S / st[0])] + st[1:]
        if st[0] in network:
            r, tries = run_with_retry(cmd)
        else:
            r, tries = subprocess.run(cmd, capture_output=True, text=True), 1
        note = f" (after {tries} attempts)" if tries > 1 else ""
        print(f"{st[0]}: exit {r.returncode}{note}\n{(r.stdout or '').strip()[-300:]}\n{(r.stderr or '').strip()[-300:]}")
        rc = rc or r.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
