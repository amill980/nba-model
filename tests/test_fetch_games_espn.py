"""The ESPN team game-log fetcher: parsing a box score into nba_api's layout, season and date handling, and the merge rules."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_games_espn as f  # noqa: E402


def box(fg, tp, ft, reb, oreb, dreb, ast, stl, blk, to_total, fouls):
    names = {"fieldGoalsMade-fieldGoalsAttempted": fg, "threePointFieldGoalsMade-threePointFieldGoalsAttempted": tp, "freeThrowsMade-freeThrowsAttempted": ft,
             "totalRebounds": reb, "offensiveRebounds": oreb, "defensiveRebounds": dreb, "assists": ast, "steals": stl, "blocks": blk, "totalTurnovers": to_total, "fouls": fouls}
    return [{"name": k, "displayValue": str(v)} for k, v in names.items()]


def summary(periods=4, away=("GS", 100, "48-91"), home=("PHI", 110, "41-80")):
    comp = lambda side, t, score: {"homeAway": side, "team": {"abbreviation": t}, "score": str(score), "linescores": [{"displayValue": "25"}] * periods}
    return {
        "header": {"id": "401909985", "competitions": [{"competitors": [comp("away", away[0], away[1]), comp("home", home[0], home[1])]}]},
        "boxscore": {"teams": [{"homeAway": "away", "statistics": box(away[2], "8-32", "20-23", 40, 8, 32, 32, 5, 3, 10, 22)},
                               {"homeAway": "home", "statistics": box(home[2], "21-67", "27-30", 45, 10, 35, 25, 7, 4, 12, 20)}]},
    }


def test_a_box_score_becomes_two_rows_in_the_nba_api_layout():
    away, home = f.game_rows(summary(), "2026-11-15", "22026")
    assert list(away) == f.COLUMNS
    assert (away["TEAM_ABBREVIATION"], away["MATCHUP"], away["WL"], away["PTS"], away["PLUS_MINUS"]) == ("GSW", "GSW @ PHI", "L", 100, -10)   # ESPN calls them GS
    assert (home["TEAM_ABBREVIATION"], home["MATCHUP"], home["WL"], home["PTS"], home["PLUS_MINUS"]) == ("PHI", "PHI vs. GSW", "W", 110, 10)
    assert (away["FGM"], away["FGA"], away["FG3M"], away["FG3A"], away["FTM"], away["FTA"]) == (48, 91, 8, 32, 20, 23)
    assert (away["OREB"], away["DREB"], away["REB"], away["AST"], away["TOV"], away["PF"]) == (8, 32, 40, 32, 10, 22)
    assert away["TEAM_ID"] == 1610612744 and away["TEAM_NAME"] == "Golden State Warriors" and away["SEASON_ID"] == "22026" and away["GAME_ID"] == "401909985"


def test_overtime_adds_25_minutes_per_extra_period_as_in_nba_api():
    assert f.game_rows(summary(4), "2026-11-15", "22026")[0]["MIN"] == 240
    assert f.game_rows(summary(5), "2026-11-15", "22026")[0]["MIN"] == 265
    assert f.game_rows(summary(6), "2026-11-15", "22026")[0]["MIN"] == 290


def test_every_espn_abbreviation_that_differs_maps_to_a_nba_team():
    for espn, nba in f.ESPN_TO_NBA.items():
        assert nba in f.TEAMS and espn not in f.TEAMS
    assert len(f.TEAMS) == 30 and f.TEAMS["LAC"][1] == "LA Clippers"


def test_percentages_round_halves_up_like_nba_api():
    assert f.pct(41, 80) == 0.513     # 0.5125: Python's round() would give 0.512
    assert f.pct(21, 67) == 0.313 and f.pct(40, 88) == 0.455 and f.pct(0, 0) == 0.0


def test_only_finished_regular_season_games_are_kept():
    sb = {"events": [
        {"id": "1", "status": {"type": {"completed": True}}, "season": {"type": 2}},
        {"id": "2", "status": {"type": {"completed": False}}, "season": {"type": 2}},       # not finished
        {"id": "3", "status": {"type": {"completed": True}}, "season": {"type": 1}},        # preseason
        {"id": "4", "status": {"type": {"completed": True}}},                               # no season type: not trusted
    ]}
    assert f.finished_regular_season(sb) == ["1"]


def test_the_season_follows_the_calendar():
    assert f.current_season(dt.date(2026, 11, 16)) == "2026-27" and f.current_season(dt.date(2027, 4, 10)) == "2026-27"
    assert f.current_season(dt.date(2026, 9, 1)) == "2026-27" and f.current_season(dt.date(2026, 8, 31)) == "2025-26"
    assert f.season_start("2026-27") == dt.date(2026, 10, 1)


def rows(date, gid):
    return pd.DataFrame({"GAME_DATE": [date, date], "GAME_ID": [gid, gid], "PTS": [1, 2]})


def test_the_merge_replaces_fetched_dates_and_never_loses_other_games():
    old = pd.concat([rows("2026-11-10", "a"), rows("2026-11-14", "b"), rows("2026-11-15", "c")], ignore_index=True)
    new = rows("2026-11-14", "b2")                                       # ESPN returned a corrected box score for the 14th, nothing for the 15th
    out = f.merge_keep(old, new, "2026-11-14")
    assert sorted(set(out.GAME_ID)) == ["a", "b2", "c"]                  # the 14th was replaced; the 15th kept because ESPN returned nothing for it
    out2 = f.merge_keep(old, new, "2026-11-15")                          # an old date before `since` is never dropped
    assert set(out2.GAME_ID) >= {"a", "c"}


def test_the_through_option_picks_the_last_date_to_fetch():
    today = dt.date(2026, 11, 16)
    assert f.through_date("today", today) == today and f.through_date("yesterday", today) == dt.date(2026, 11, 15)
    assert f.through_date("2026-11-10", today) == dt.date(2026, 11, 10)


def test_trim_keeps_nothing_after_the_cutoff_even_if_an_earlier_run_left_it_in_the_file(tmp_path):
    out = tmp_path / "team_games_2026-27_Regular_Season.csv"
    old = pd.concat([rows("2026-11-14", "a"), rows("2026-11-16", "today_from_the_noon_run")], ignore_index=True)
    old.to_csv(out, index=False)
    merged = f.merge_keep(pd.read_csv(out, dtype={"GAME_ID": str}), pd.DataFrame(columns=old.columns), "2026-11-11")   # a fetch through yesterday that found nothing new
    trimmed = merged[merged.GAME_DATE <= f.through_date("yesterday", dt.date(2026, 11, 16)).isoformat()]
    assert set(trimmed.GAME_ID) == {"a"} and "today_from_the_noon_run" in set(merged.GAME_ID)
