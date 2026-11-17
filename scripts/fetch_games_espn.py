"""Fetch NBA team game logs (one row per team per game) from ESPN's public feeds, in the same layout as `fetch_games.py` writes from nba_api.

Why: stats.nba.com drops connections from cloud servers (checked from a GitHub Actions runner, 2026-11-16: every call timed out), but ESPN's
site API answers from anywhere. The model's ratings need only team box scores, and ESPN carries every figure they use (field goals, threes,
free throws, offensive and total rebounds, turnovers, points). Before the cloud run uses this file the output is compared with the nba_api
file game by game (scripts/compare_espn_games.py): it is used only if every figure matches.

Output columns are those of the nba_api file. Differences, all internal to the file: GAME_ID is ESPN's event id (nba_api's is an NBA id), and
TEAM_ID / TEAM_NAME come from the fixed table below. MIN is 240 plus 25 per overtime period, as in nba_api's team logs. PLUS_MINUS is the
team's points minus its opponent's. Only finished regular-season games are written (ESPN season type 2).

Usage: python scripts/fetch_games_espn.py --season 2026-27 --out data/games/team_games_2026-27_Regular_Season.csv
       [--since YYYY-MM-DD] [--keep]   (--keep: read the existing --out file, keep its games before --since, replace the rest)
Reads nothing but ESPN's feeds; needs only the standard library and pandas.
"""
import argparse
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
UA = {"User-Agent": "fairline-nba-logs/1.0"}  # an honest name; ESPN's edge answers 403 to user-agents that contain "fetch"
COLUMNS = ["SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "GAME_ID", "GAME_DATE", "MATCHUP", "WL", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A",
           "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS", "VIDEO_AVAILABLE"]

TEAMS = {
    "ATL": (1610612737, "Atlanta Hawks"), "BKN": (1610612751, "Brooklyn Nets"), "BOS": (1610612738, "Boston Celtics"), "CHA": (1610612766, "Charlotte Hornets"),
    "CHI": (1610612741, "Chicago Bulls"), "CLE": (1610612739, "Cleveland Cavaliers"), "DAL": (1610612742, "Dallas Mavericks"), "DEN": (1610612743, "Denver Nuggets"),
    "DET": (1610612765, "Detroit Pistons"), "GSW": (1610612744, "Golden State Warriors"), "HOU": (1610612745, "Houston Rockets"), "IND": (1610612754, "Indiana Pacers"),
    "LAC": (1610612746, "LA Clippers"), "LAL": (1610612747, "Los Angeles Lakers"), "MEM": (1610612763, "Memphis Grizzlies"), "MIA": (1610612748, "Miami Heat"),
    "MIL": (1610612749, "Milwaukee Bucks"), "MIN": (1610612750, "Minnesota Timberwolves"), "NOP": (1610612740, "New Orleans Pelicans"), "NYK": (1610612752, "New York Knicks"),
    "OKC": (1610612760, "Oklahoma City Thunder"), "ORL": (1610612753, "Orlando Magic"), "PHI": (1610612755, "Philadelphia 76ers"), "PHX": (1610612756, "Phoenix Suns"),
    "POR": (1610612757, "Portland Trail Blazers"), "SAC": (1610612758, "Sacramento Kings"), "SAS": (1610612759, "San Antonio Spurs"), "TOR": (1610612761, "Toronto Raptors"),
    "UTA": (1610612762, "Utah Jazz"), "WAS": (1610612764, "Washington Wizards"),
}
# ESPN's abbreviations that differ from the NBA's.
ESPN_TO_NBA = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}


def get_json(url: str, attempts: int = 3) -> dict:
    last = None
    for n in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception as exc:  # network error or bad JSON: retry, then give up
            last = exc
            time.sleep(2 * (n + 1))
    raise RuntimeError(f"{url}: {type(last).__name__}: {last}")


def pair(text: str) -> tuple[int, int]:
    made, att = text.split("-")
    return int(made), int(att)


def stat(team_box: dict) -> dict:
    return {s["name"]: s["displayValue"] for s in team_box["statistics"]}


def pct(made: int, att: int) -> float:
    """made / att to three places, halves rounded up as nba_api rounds them (Python's round() would turn 41/80 = 0.5125 into 0.512, nba_api gives 0.513)."""
    return float((Decimal(made) / Decimal(att)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)) if att else 0.0


def game_rows(summary: dict, date: str, season_id: str) -> list[dict]:
    """Two rows (one per team) for one finished game's summary payload."""
    comp = summary["header"]["competitions"][0]
    comps = {c["homeAway"]: c for c in comp["competitors"]}
    boxes = {t["homeAway"]: t for t in summary["boxscore"]["teams"]}
    periods = max(len(c.get("linescores", [])) for c in comp["competitors"])
    minutes = 240 + 25 * max(0, periods - 4)
    abbr = {side: ESPN_TO_NBA.get(comps[side]["team"]["abbreviation"], comps[side]["team"]["abbreviation"]) for side in comps}
    pts = {side: int(comps[side]["score"]) for side in comps}
    event_id = str(summary["header"]["id"])
    rows = []
    for side, other in (("away", "home"), ("home", "away")):
        s = stat(boxes[side])
        fgm, fga = pair(s["fieldGoalsMade-fieldGoalsAttempted"])
        fg3m, fg3a = pair(s["threePointFieldGoalsMade-threePointFieldGoalsAttempted"])
        ftm, fta = pair(s["freeThrowsMade-freeThrowsAttempted"])
        me, opp = abbr[side], abbr[other]
        tid, name = TEAMS[me]
        rows.append({
            "SEASON_ID": season_id, "TEAM_ID": tid, "TEAM_ABBREVIATION": me, "TEAM_NAME": name, "GAME_ID": event_id, "GAME_DATE": date,
            "MATCHUP": f"{me} @ {opp}" if side == "away" else f"{me} vs. {opp}", "WL": "W" if pts[side] > pts[other] else "L", "MIN": minutes,
            "FGM": fgm, "FGA": fga, "FG_PCT": pct(fgm, fga), "FG3M": fg3m, "FG3A": fg3a, "FG3_PCT": pct(fg3m, fg3a), "FTM": ftm, "FTA": fta, "FT_PCT": pct(ftm, fta),
            "OREB": int(s["offensiveRebounds"]), "DREB": int(s["defensiveRebounds"]), "REB": int(s["totalRebounds"]), "AST": int(s["assists"]),
            "STL": int(s["steals"]), "BLK": int(s["blocks"]), "TOV": int(s["totalTurnovers"]), "PF": int(s["fouls"]), "PTS": pts[side],
            "PLUS_MINUS": pts[side] - pts[other], "VIDEO_AVAILABLE": 1,
        })
    return rows


def finished_regular_season(scoreboard: dict) -> list[str]:
    """Event ids of the finished regular-season games on a scoreboard (preseason and tournament knockout games are not regular season)."""
    out = []
    for e in scoreboard.get("events", []):
        if not e["status"]["type"].get("completed"):
            continue
        if (e.get("season") or {}).get("type") != 2:
            continue
        out.append(str(e["id"]))
    return out


def fetch(start: dt.date, end: dt.date, season_id: str, pause: float = 0.15) -> pd.DataFrame:
    rows, day = [], start
    while day <= end:
        sb = get_json(f"{BASE}/scoreboard?dates={day:%Y%m%d}")
        for eid in finished_regular_season(sb):
            rows += game_rows(get_json(f"{BASE}/summary?event={eid}"), day.isoformat(), season_id)
            time.sleep(pause)
        day += dt.timedelta(days=1)
    return pd.DataFrame(rows, columns=COLUMNS)


def season_start(season: str) -> dt.date:
    return dt.date(int(season[:4]), 10, 1)


def eastern_today() -> dt.date:
    """Today's date in Eastern time, which is how ESPN's scoreboard days and nba_api's game dates are cut."""
    from zoneinfo import ZoneInfo

    return dt.datetime.now(ZoneInfo("America/New_York")).date()


def current_season(today: dt.date) -> str:
    """The season a date falls in ('2026-27' from September 2026 to August 2027)."""
    y = today.year if today.month >= 9 else today.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def through_date(text: str, today: dt.date) -> dt.date:
    """The last date to fetch: 'today', 'yesterday' or an ISO date."""
    if text == "today":
        return today
    if text == "yesterday":
        return today - dt.timedelta(days=1)
    return dt.date.fromisoformat(text)


def merge_keep(old: pd.DataFrame, new: pd.DataFrame, since: str) -> pd.DataFrame:
    """The fetched games replace the old ones for the dates they cover (so a corrected box score wins); everything else in `old` stays. A date
    before `since` is never touched, and a date ESPN returned nothing for keeps its old rows rather than losing them."""
    keep = old[(old.GAME_DATE < since) | ~old.GAME_DATE.isin(new.GAME_DATE)]
    return pd.concat([keep, new], ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", required=True, help="e.g. 2026-27, or 'auto' for the season that is under way")
    ap.add_argument("--out", required=True, type=Path, help="output csv; '{season}' in the path is replaced by the season (e.g. 2026-27)")
    ap.add_argument("--since", help="first date to fetch, YYYY-MM-DD (default: the start of the season)")
    ap.add_argument("--since-days", type=int, help="fetch only the last N days (Eastern); with --keep, earlier games stay as they are")
    ap.add_argument("--keep", action="store_true", help="keep the games already in --out that the fetch does not cover")
    ap.add_argument("--through", default="today", help="last date to fetch: 'today' (default), 'yesterday', or YYYY-MM-DD (Eastern). The PC's own daily fetch runs at 6:30 AM, "
                    "so the model's ratings have always been built from games through yesterday; use 'yesterday' for the step that feeds the model.")
    ap.add_argument("--trim", action="store_true", help="also drop any game in --out dated after --through (the step that feeds the model must never see later games)")
    a = ap.parse_args(argv)
    today = eastern_today()
    through = through_date(a.through, today)
    season = current_season(today) if a.season == "auto" else a.season
    out = Path(str(a.out).replace("{season}", season))
    season_id = "2" + season[:4]
    if a.since_days is not None:
        start = max(today - dt.timedelta(days=a.since_days), season_start(season))
    else:
        start = dt.date.fromisoformat(a.since) if a.since else season_start(season)
    df = fetch(start, through, season_id) if start <= through else pd.DataFrame(columns=COLUMNS)
    if a.keep and out.exists():
        df = merge_keep(pd.read_csv(out, dtype={"GAME_ID": str}), df, start.isoformat())
    if a.trim:
        df = df[df.GAME_DATE <= through.isoformat()]
    df = df.sort_values(["GAME_DATE", "GAME_ID", "TEAM_ABBREVIATION"]).reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"saved {out.name}: {len(df)} team-games, {df['GAME_ID'].nunique()} games, {df.GAME_DATE.min()} to {df.GAME_DATE.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
