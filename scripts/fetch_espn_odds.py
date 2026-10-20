"""Fetch historical OPEN and CLOSE lines per sportsbook from ESPN's public core API.

For each game day: scoreboard -> events -> /events/{id}/competitions/{id}/odds. Every non-live
provider item is stored with open and close spread (home, book notation), total, and moneylines.
Cached per day in data/espn_odds/days/<YYYYMMDD>.csv (fetch-once; --refresh to redo).
Combined output: data/espn_odds/espn_lines_<season>.csv

Usage: python scripts/fetch_espn_odds.py --seasons 2023-24 [--every 10] [--refresh]
  --every N : only every Nth game day (cheap sample for a provenance probe)
Public, unauthenticated API; not an official/documented product: gate before relying on it.
"""
import argparse, csv, json, re, time, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "espn_odds"; DAYS = OUT / "days"
ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
UA = {"User-Agent": "Mozilla/5.0"}
FIELDS = ["date", "event_id", "home", "away", "provider", "spread_open", "spread_close", "total_open", "total_close",
          "ml_home_open", "ml_home_close", "ml_away_open", "ml_away_close"]


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(1 + attempt)
    return None


def num(s):
    if s is None: return None
    s = str(s).strip().upper()
    if s in ("PK", "EVEN"): return 0.0
    try: return float(s)
    except ValueError: return None


def side(d, which, key):
    try: return num(d[which][key]["american"])
    except (KeyError, TypeError): return None


def fetch_day(date):
    ymd = date.replace("-", "")
    f = DAYS / f"{ymd}.csv"
    if f.exists(): return pd.read_csv(f)
    rows = []
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={ymd}&limit=500") or {}
    for e in sb.get("events", []):
        comp = e["competitions"][0]
        t = {c["homeAway"]: ALIAS.get(c["team"]["abbreviation"], c["team"]["abbreviation"]) for c in comp["competitors"]}
        eid = e["id"]
        od = get(f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{eid}/competitions/{eid}/odds") or {}
        for it in od.get("items", []):
            name = it["provider"]["name"]
            if "live" in name.lower(): continue
            h, a = it.get("homeTeamOdds", {}), it.get("awayTeamOdds", {})
            rows.append(dict(date=date, event_id=eid, home=t.get("home"), away=t.get("away"), provider=name,
                             spread_open=side(h, "open", "pointSpread"), spread_close=side(h, "close", "pointSpread"),
                             total_open=side(it, "open", "total"), total_close=side(it, "close", "total"),
                             ml_home_open=side(h, "open", "moneyLine"), ml_home_close=side(h, "close", "moneyLine"),
                             ml_away_open=side(a, "open", "moneyLine"), ml_away_close=side(a, "close", "moneyLine")))
        time.sleep(0.1)
    df = pd.DataFrame(rows, columns=FIELDS)
    DAYS.mkdir(parents=True, exist_ok=True); df.to_csv(f, index=False)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2023-24"])
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    for s in a.seasons:
        g = pd.read_csv(ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv")
        days = sorted(g.GAME_DATE.unique())[::a.every]
        frames = []
        for i, d in enumerate(days):
            if a.refresh and (DAYS / f"{d.replace('-', '')}.csv").exists():
                (DAYS / f"{d.replace('-', '')}.csv").unlink()
            frames.append(fetch_day(d))
            if (i + 1) % 20 == 0: print(f"{s}: {i+1}/{len(days)} days", flush=True)
        df = pd.concat(frames, ignore_index=True)
        df.to_csv(OUT / f"espn_lines_{s}{'_sample' if a.every > 1 else ''}.csv", index=False)
        print(s, "rows", len(df), "events", df.event_id.nunique(), "providers", df.provider.value_counts().head(6).to_dict())


if __name__ == "__main__":
    main()
