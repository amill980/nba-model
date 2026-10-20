"""Archive one NBA odds snapshot (spreads, totals, moneylines) from The Odds API.

The key is read ONLY from the ODDS_API_KEY environment variable. It travels in the
URL, so every URL/error printed or logged is redacted. Raw JSON is saved untouched
with the capture time so the line the market showed can be reconstructed later.

Guards: skip if the newest snapshot is younger than --min-interval-min; refuse if
the API reports fewer than --reserve credits remaining.

Usage:  python scripts/archive_odds.py [--regions us,us2] [--dry-run]
"""
import argparse, csv, json, os, re, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "odds" / "raw"
LOG = ROOT / "data" / "odds" / "quota_log.csv"
SPORT = "basketball_nba"
DEFAULT_MARKETS = "h2h,spreads,totals"


def redact(text, key):
    text = text.replace(key, "REDACTED") if key else text
    return re.sub(r"apiKey=[^&\s]+", "apiKey=REDACTED", text)


def newest_snapshot_age_min():
    files = sorted(RAW.glob("*.json"))
    if not files:
        return None
    last = datetime.strptime(files[-1].stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() / 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", default="us,us2")
    ap.add_argument("--markets", default=DEFAULT_MARKETS)
    ap.add_argument("--only-if-games", action="store_true", help="skip unless an NBA game starts within --window-hours (uses the free /events endpoint, 0 credits)")
    ap.add_argument("--window-hours", type=float, default=14)
    ap.add_argument("--min-interval-min", type=float, default=15)
    ap.add_argument("--reserve", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = os.environ.get("ODDS_API_KEY", "")
    if not key:
        sys.exit("ODDS_API_KEY is not set.")
    RAW.mkdir(parents=True, exist_ok=True)

    age = newest_snapshot_age_min()
    if age is not None and age < a.min_interval_min:
        print(f"Skipped: newest snapshot is {age:.1f} min old (< {a.min_interval_min}).")
        return

    if LOG.exists():
        last = list(csv.DictReader(LOG.open(newline="")))[-1]
        if last["credits_remaining"] and int(last["credits_remaining"]) < a.reserve:
            print(f"Skipped: last known credits remaining ({last['credits_remaining']}) "
                  f"below reserve ({a.reserve}).")
            return

    if a.only_if_games and not a.dry_run:
        ev_url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events?dateFormat=iso&apiKey={key}"
        try:
            with urllib.request.urlopen(ev_url, timeout=30) as r:
                events = json.loads(r.read())
        except Exception as e:
            sys.exit(f"Events request failed: {redact(repr(e), key)}")
        now = datetime.now(timezone.utc)
        soon = [e for e in events if 0 <= (datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) - now).total_seconds() / 3600 <= a.window_hours]
        if not soon:
            print(f"Skipped: no NBA game starts within {a.window_hours} h (events call is free)."); return

    url = (f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds?regions={a.regions}"
           f"&markets={a.markets}&oddsFormat=american&dateFormat=iso&apiKey={key}")
    cost = len(a.markets.split(",")) * len(a.regions.split(","))
    if a.dry_run:
        print("Would call:", redact(url, key), f"(cost {cost} credits)")
        return
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read()
            remaining = r.headers.get("x-requests-remaining")
            used = r.headers.get("x-requests-used")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {redact(str(e.reason), key)}")
    except Exception as e:  # never let the key leak through an error message
        sys.exit(f"Request failed: {redact(repr(e), key)}")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    (RAW / f"{stamp}.json").write_bytes(body)
    games = json.loads(body)
    new_log = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new_log:
            w.writerow(["captured_utc", "regions", "games", "credits_used_total", "credits_remaining"])
        w.writerow([stamp, a.regions, len(games), used, remaining])
    print(f"(markets={a.markets}, call cost about {cost} credits)")
    print(f"Saved {stamp}.json: {len(games)} games. Credits remaining: {remaining}.")
    if remaining is not None and int(remaining) < a.reserve:
        print(f"WARNING: remaining credits below reserve ({a.reserve}).")


if __name__ == "__main__":
    main()
