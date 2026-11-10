"""Fetch every team's current roster (30 calls) and keep dated snapshots, so trades and signings are visible.

Output: data/rosters/roster_<YYYY-MM-DD>.csv   one row per player on a roster that day
        data/rosters/roster_latest.csv         copy of the newest snapshot (what the profile builder reads)
        data/rosters/roster_changes.csv        appended when a player joins, leaves or changes team vs the previous snapshot

Each team call is retried (stats.nba.com drops connections often). If fewer than 30 teams succeed, nothing is
saved over the previous snapshot. Usage: python scripts/fetch_rosters.py [--season 2026-27]
"""
import argparse, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "rosters"
KEEP = ["TeamID", "PLAYER", "PLAYER_ID", "NUM", "POSITION", "HEIGHT", "WEIGHT", "BIRTH_DATE", "AGE", "EXP", "SCHOOL", "HOW_ACQUIRED"]


def height_inches(h):
    try:
        f, i = str(h).split("-"); return int(f) * 12 + int(i)
    except Exception:
        return None


def diff_rosters(old, new, day):
    """Rows describing who joined, left or changed team between two snapshots (DataFrames with PLAYER_ID, PLAYER, TEAM)."""
    o = dict(zip(old.PLAYER_ID, zip(old.PLAYER, old.TEAM))); n = dict(zip(new.PLAYER_ID, zip(new.PLAYER, new.TEAM))); rows = []
    for pid, (name, team) in n.items():
        if pid not in o: rows.append((day, name, pid, "joined roster", "", team))
        elif o[pid][1] != team: rows.append((day, name, pid, "changed team", o[pid][1], team))
    for pid, (name, team) in o.items():
        if pid not in n: rows.append((day, name, pid, "left roster", team, ""))
    return pd.DataFrame(rows, columns=["date", "player", "player_id", "change", "from_team", "to_team"])


def main():
    from nba_api.stats.static import teams
    from nba_api.stats.endpoints import commonteamroster
    ap = argparse.ArgumentParser(); ap.add_argument("--season", default="2026-27"); a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    frames, failed = [], []
    for t in teams.get_teams():
        for attempt in range(3):
            try:
                df = commonteamroster.CommonTeamRoster(team_id=t["id"], season=a.season, timeout=60).get_data_frames()[0]
                df = df[KEEP].copy(); df["TEAM"] = t["abbreviation"]; frames.append(df); break
            except Exception:
                time.sleep(5 * (attempt + 1))
        else:
            failed.append(t["abbreviation"])
        time.sleep(1)
    if failed:
        print(f"{len(failed)} teams failed ({', '.join(failed)}); keeping the previous snapshot."); raise SystemExit(1)
    new = pd.concat(frames, ignore_index=True)
    new["HEIGHT_IN"] = new.HEIGHT.map(height_inches)
    day = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    latest = OUT / "roster_latest.csv"
    if latest.exists():
        ch = diff_rosters(pd.read_csv(latest), new, day)
        if len(ch):
            log = OUT / "roster_changes.csv"
            ch.to_csv(log, mode="a", header=not log.exists(), index=False)
            print(f"{len(ch)} roster change(s) since the last snapshot")
    new.to_csv(OUT / f"roster_{day}.csv", index=False); new.to_csv(latest, index=False)
    print(f"saved roster_{day}.csv: {len(new)} players on 30 rosters")


if __name__ == "__main__":
    main()
