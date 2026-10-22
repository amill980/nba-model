"""Checks of the daily fetch's retry and staleness logic (no network).
Run: .venv\\Scripts\\python.exe tests\\test_daily_fetch.py
"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import daily_fetch as df  # noqa: E402


def fake_runner(codes):
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=codes[min(len(calls) - 1, len(codes) - 1)], stdout="", stderr="")
    runner.calls = calls
    return runner


def test_succeeds_first_time_without_waiting():
    waits = []
    r, n = df.run_with_retry(["x"], fake_runner([0]), waits.append)
    assert r.returncode == 0 and n == 1 and waits == []


def test_retries_after_failures_and_waits_between_attempts():
    waits, runner = [], fake_runner([1, 1, 0])
    r, n = df.run_with_retry(["x"], runner, waits.append)
    assert r.returncode == 0 and n == 3 and len(runner.calls) == 3 and waits == [45, 120]


def test_gives_up_after_the_attempts_and_reports_the_failure():
    waits, runner = [], fake_runner([1])
    r, n = df.run_with_retry(["x"], runner, waits.append)
    assert r.returncode == 1 and n == 3 and len(runner.calls) == 3 and waits == [45, 120]


def test_staleness_uses_eastern_dates():
    now = datetime(2026, 10, 22, 11, 30, tzinfo=ZoneInfo("America/New_York"))
    assert df.is_stale("2026-10-20", now) is True            # two days behind
    assert df.is_stale("2026-10-21", now) is False           # yesterday's games are in
    assert df.is_stale("2026-10-22", now) is False
    assert df.is_stale(None, now) is True


def test_newest_player_game_reads_the_season_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "data" / "players").mkdir(parents=True)
        (root / "data" / "players" / "player_games_2026-27.csv").write_text("GAME_DATE,PTS\n2026-10-20,10\n2026-10-21,12\n",
                                                                           encoding="utf-8")
        assert df.newest_player_game("2026-27", root) == "2026-10-21"
        assert df.newest_player_game("2025-26", root) is None


if __name__ == "__main__":
    test_succeeds_first_time_without_waiting()
    test_retries_after_failures_and_waits_between_attempts()
    test_gives_up_after_the_attempts_and_reports_the_failure()
    test_staleness_uses_eastern_dates()
    test_newest_player_game_reads_the_season_file()
    print("ALL PASS")
