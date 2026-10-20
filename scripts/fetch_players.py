"""Fetch player game logs (one row per player per game) via nba_api; fetch-once per season.
Output: data/players/player_games_<season>.csv. Use --refresh to redo a season."""
import argparse, time
from pathlib import Path
from nba_api.stats.endpoints import leaguegamelog
OUT = Path(__file__).resolve().parent.parent / "data" / "players"
ap = argparse.ArgumentParser(); ap.add_argument("--seasons", nargs="+", default=["2022-23", "2023-24", "2024-25", "2025-26"]); ap.add_argument("--refresh", action="store_true")
a = ap.parse_args(); OUT.mkdir(parents=True, exist_ok=True)
for s in a.seasons:
    f = OUT / f"player_games_{s}.csv"
    if f.exists() and not a.refresh: print("skip", f.name); continue
    df = leaguegamelog.LeagueGameLog(season=s, season_type_all_star="Regular Season", player_or_team_abbreviation="P", timeout=90).get_data_frames()[0]
    df.to_csv(f, index=False); print(f"saved {f.name}: {len(df)} player-games, {df.PLAYER_ID.nunique()} players, {df.GAME_ID.nunique()} games"); time.sleep(2)
