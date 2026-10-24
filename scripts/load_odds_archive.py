"""Flatten archived Odds API snapshots (data/odds/raw/*.json) into one tidy table.

Output: data/odds/odds_archive.csv, one row per (snapshot, event, book, market, outcome):
  captured_utc, event_id, commence_time_utc, game_date_et, home, away, book, market,
  last_update_utc, outcome, price, point
Team names are mapped to nba_api abbreviations; an unmapped name stops the run (never guess).
Also writes data/odds/archive_summary.txt (snapshots per game day, books seen).
Run after each snapshot (or on demand); safe to re-run, the table is rebuilt from the raw files.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "odds" / "raw"
OUT = ROOT / "data" / "odds"
TEAMS = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS"}
ET = ZoneInfo("America/New_York")


def abbr(name):
    if name not in TEAMS:
        raise SystemExit(f"Unmapped team name {name!r}: add it to TEAMS (no guessing).")
    return TEAMS[name]


def main():
    rows = []
    files = sorted(RAW.glob("*.json"))
    for f in files:
        cap = datetime.strptime(f.stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        for ev in json.loads(f.read_text()):
            commence = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            home, away = abbr(ev["home_team"]), abbr(ev["away_team"])
            for bk in ev.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    for oc in mk.get("outcomes", []):
                        team = oc["name"]
                        outcome = team if team in ("Over", "Under") else ("home" if abbr(team) == home else "away")
                        rows.append(dict(captured_utc=cap.strftime("%Y-%m-%dT%H:%M:%SZ"), event_id=ev["id"],
                                         commence_time_utc=commence.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                         game_date_et=commence.astimezone(ET).strftime("%Y-%m-%d"), home=home, away=away,
                                         book=bk["key"], market=mk["key"], last_update_utc=mk.get("last_update"),
                                         outcome=outcome, price=oc.get("price"), point=oc.get("point")))
    df = pd.DataFrame(rows)
    if len(df):
        # The Odds API also returns IN-PLAY lines for games already started (e.g. a 27.5-point spread mid-game), so every row is
        # flagged: pregame = captured before the scheduled tip. Anything that means "the market line" must use pregame rows only.
        df["pregame"] = pd.to_datetime(df.captured_utc, utc=True) < pd.to_datetime(df.commence_time_utc, utc=True)
        # Locked closing line: for each game, the last pregame snapshot, with how many minutes before tip it was taken.
        pre = df[df.pregame]
        last = pre.groupby("event_id").captured_utc.transform("max")
        close = pre[pre.captured_utc == last].copy()
        close = close[pd.to_datetime(close.commence_time_utc, utc=True) <= pd.Timestamp.now(tz="UTC")]   # only games already started have a locked close
        close["minutes_before_tip"] = ((pd.to_datetime(close.commence_time_utc, utc=True) - pd.to_datetime(close.captured_utc, utc=True)).dt.total_seconds() / 60).round(1)
        close["close_quality"] = close.minutes_before_tip.map(lambda m: "locked (<=20 min)" if m <= 20 else "stale (>20 min before tip)")
        close.drop(columns=["pregame"]).to_csv(OUT / "closing_lines.csv", index=False)
    df.to_csv(OUT / "odds_archive.csv", index=False)
    lines = [f"snapshots: {len(files)}; rows: {len(df)}"]
    if len(df):
        lines.append("books: " + ", ".join(sorted(df.book.unique())))
        lines.append("snapshots per ET game date:\n" + df.groupby("game_date_et").captured_utc.nunique().to_string())
    (OUT / "archive_summary.txt").write_text("\n".join(lines))
    print("\n".join(lines[:2]))


if __name__ == "__main__":
    main()
