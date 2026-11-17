"""The cloud run's state helper: restore puts the state branch's files where the scripts read them, save brings a run's changes back."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cloud_state as cs  # noqa: E402


def write(p: Path, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_restore_puts_every_part_where_the_scripts_read_it(tmp_path):
    state, root = tmp_path / "state", tmp_path / "work"
    write(state / "games" / "team_games_2025-26_Regular_Season.csv", "g")
    write(state / "odds_history" / "nba_betting_data_2007_2026" / "nba_2008-2026.csv", "h")
    write(state / "espn_odds" / "days" / "20260101.csv", "e")
    write(state / "odds" / "quota_log.csv", "q")
    write(state / "odds" / "raw" / "20261116T170000Z.json", "{}")
    write(state / "daily_reports" / "2026-11-15.json", "{}")
    counts = cs.restore(state, root)
    assert (root / "data/games/team_games_2025-26_Regular_Season.csv").read_text() == "g"
    assert (root / "data/odds_history/nba_betting_data_2007_2026/nba_2008-2026.csv").read_text() == "h"
    assert (root / "data/espn_odds/days/20260101.csv").is_file() and (root / "data/odds/quota_log.csv").read_text() == "q"
    assert (root / "data/odds/raw/20261116T170000Z.json").is_file() and (root / "reports/daily/2026-11-15.json").is_file()
    assert counts["games"] == 1 and counts["daily_reports"] == 1 and counts["odds/quota_log.csv"] == 1


def test_restore_gives_daily_projections_a_valid_empty_odds_table_on_a_first_run(tmp_path):
    cs.restore(tmp_path / "empty_state", tmp_path / "work")                      # nothing in the state yet
    table = tmp_path / "work" / "data" / "odds" / "odds_archive.csv"
    assert table.read_text(encoding="utf-8") == cs.ARCHIVE_HEADER and (tmp_path / "work/data/odds/raw").is_dir()
    write(table, cs.ARCHIVE_HEADER + "a,b\n")
    cs.restore(tmp_path / "empty_state", tmp_path / "work")                      # an existing table is never overwritten
    assert table.read_text(encoding="utf-8").endswith("a,b\n")


def test_restore_overwrites_a_tracked_daily_report_with_the_states_version(tmp_path):
    state, root = tmp_path / "state", tmp_path / "work"
    write(root / "reports/daily/2026-11-15.json", "tracked, older")
    write(state / "daily_reports" / "2026-11-15.json", "state, final")
    cs.restore(state, root)
    assert (root / "reports/daily/2026-11-15.json").read_text() == "state, final"


def test_save_brings_back_this_runs_changes_and_leaves_static_files_alone(tmp_path):
    state, root = tmp_path / "state", tmp_path / "work"
    write(root / "data/games/team_games_2026-27_Regular_Season.csv", "new season file")
    write(root / "data/odds/quota_log.csv", "log")
    write(root / "data/odds/raw/20261116T230000Z.json", "{}")
    write(root / "reports/daily/2026-11-16.json", "{}")
    write(root / "data/espn_odds/days/20260101.csv", "static")
    write(root / "data/odds_history/x/nba_2008-2026.csv", "static")
    cs.save(state, root)
    assert (state / "games/team_games_2026-27_Regular_Season.csv").read_text() == "new season file"
    assert (state / "odds/quota_log.csv").read_text() == "log" and (state / "odds/raw/20261116T230000Z.json").is_file()
    assert (state / "daily_reports/2026-11-16.json").is_file()
    assert not (state / "espn_odds").exists() and not (state / "odds_history").exists()   # static parts are never written back


def test_save_drops_old_snapshots_from_the_state_but_keeps_recent_ones(tmp_path):
    state, root = tmp_path / "state", tmp_path / "work"
    old, recent = write(state / "odds/raw/old.json"), write(state / "odds/raw/recent.json")
    now = time.time()
    os.utime(old, (now - 5 * 86400, now - 5 * 86400))
    os.utime(recent, (now - 1 * 86400, now - 1 * 86400))
    counts = cs.save(state, root, keep_raw_days=3, now=now)
    assert not old.exists() and recent.exists() and counts["old snapshots removed"] == 1


def test_a_round_trip_returns_the_same_files(tmp_path):
    state, root = tmp_path / "state", tmp_path / "work"
    write(state / "games" / "team_games_2026-27_Regular_Season.csv", "A")
    write(state / "daily_reports" / "2026-11-15.json", "B")
    cs.restore(state, root)
    write(root / "reports/daily/2026-11-16.json", "C")                           # a new day's report
    cs.save(state, root)
    assert (state / "daily_reports/2026-11-15.json").read_text() == "B" and (state / "daily_reports/2026-11-16.json").read_text() == "C"
    assert (state / "games/team_games_2026-27_Regular_Season.csv").read_text() == "A"
