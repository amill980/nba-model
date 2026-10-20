"""Fetch NBA team game logs (one row per team per game) via nba_api and save raw CSVs.

Fetch-once: a season file that already exists is skipped unless --refresh is given.
Output: data/games/team_games_<season>_<type>.csv   (e.g. team_games_2023-24_Regular_Season.csv)

Usage: python scripts/fetch_games.py [--seasons 2022-23 2023-24 ...] [--refresh]
"""
import argparse, time
from pathlib import Path

from nba_api.stats.endpoints import leaguegamelog

OUT = Path(__file__).resolve().parent.parent / "data" / "games"
DEFAULT = ["2022-23", "2023-24", "2024-25", "2025-26"]
TYPES = ["Regular Season", "Playoffs"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=DEFAULT)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for season in a.seasons:
        for st in TYPES:
            f = OUT / f"team_games_{season}_{st.replace(' ', '_')}.csv"
            if f.exists() and not a.refresh:
                print("skip (exists):", f.name)
                continue
            df = leaguegamelog.LeagueGameLog(
                season=season, season_type_all_star=st,
                player_or_team_abbreviation="T", timeout=60).get_data_frames()[0]
            df.to_csv(f, index=False)
            print(f"saved {f.name}: {len(df)} team-games, {df['GAME_ID'].nunique()} games")
            time.sleep(2)


if __name__ == "__main__":
    main()
