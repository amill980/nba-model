"""The ESPN fallback report: parsing ESPN's odds, the median over providers, which games are listed, and what it leaves alone."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import espn_fallback_report as f  # noqa: E402

NOW = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)


def item(provider="DraftKings", spread="+2.5", total="212.5"):
    return {"provider": {"name": provider}, "homeTeamOdds": {"current": {"pointSpread": {"american": spread}}},
            "current": {"total": {"alternateDisplayValue": total}}}


def test_current_lines_read_the_home_spread_and_the_total():
    assert f.current_lines({"items": [item()]}) == [("DraftKings", 2.5, 212.5)]
    assert f.current_lines({"items": [item(spread="-6.5", total="o221.5")]}) == [("DraftKings", -6.5, None)]    # an odd total is skipped, not guessed
    assert f.current_lines({"items": [item(spread="PK")]})[0][1] == 0.0


def test_in_play_and_empty_providers_are_dropped():
    items = [item(), item(provider="ESPN Bet - Live Odds", spread="-30.5"), {"provider": {"name": "Empty"}}]
    assert [p for p, _, _ in f.current_lines({"items": items})] == ["DraftKings"]
    assert f.current_lines(None) == [] and f.current_lines({}) == []


def test_the_market_is_the_median_and_counts_the_books():
    assert f.market([("A", -6.0, 150.0), ("B", -7.0, 152.0), ("C", -8.0, 154.0)]) == (-7.0, 152.0, 3)
    assert f.market([("A", -6.5, None)]) == (-6.5, None, 1)
    assert f.market([]) == (None, None, 0)


def ratings():
    cols = dict(bo=[112.0, 108.0], bd=[110.0, 114.0], bp=[99.0, 97.0], gp=[10, 10])
    return pd.DataFrame(cols, index=["CHA", "MEM"]), 111.0, pd.DataFrame()


def event(eid, home, away, state="pre", date="2026-11-24T00:00Z"):
    return {"id": eid, "date": date, "status": {"type": {"state": state}},
            "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": home}},
                                              {"homeAway": "away", "team": {"abbreviation": away}}]}]}


def test_rows_cover_unstarted_games_with_a_line_in_the_reports_shape():
    R, lg, gc = ratings()
    events = [event("1", "CHA", "MEM"), event("2", "CHA", "MEM", state="in"), event("3", "CHA", "MEM", date="2026-11-23T17:00Z"),
              event("4", "CHA", "MEM")]
    odds = {"1": [("DraftKings", 2.5, 212.5)], "2": [("DraftKings", 2.5, 212.5)], "3": [("DraftKings", 2.5, 212.5)], "4": []}
    rows = f.build_rows("2026-11-23", events, odds, R, lg, gc, NOW)
    assert len(rows) == 1                                  # in progress, already tipped and line-less games are left out
    r = rows[0]
    assert r["game"] == "MEM @ CHA" and r["tip_et"] == "07:00 PM" and r["n_books"] == "1"
    assert r["consensus_home_spread"] == "2.5" and r["consensus_total"] == "212.5" and r["spread_flag"] == "" and r["total_flag"] == ""
    game = f.ep.build_game(r)                              # the report writer accepts it, and no lean is shown
    assert game["market_home_spread"] == 2.5 and game["lean"] == "" and game["total_lean"] == "" and game["n_books"] == 1


def test_the_model_line_is_the_frozen_formula():
    R, lg, gc = ratings()
    margin, total = f.model_line(R, lg, gc, "CHA", "MEM", "2026-11-23")
    pace = 98.0
    hp, ap_ = pace * (112.0 + 114.0 - 111.0) / 100, pace * (108.0 + 110.0 - 111.0) / 100
    assert abs(total - (hp + ap_)) < 1e-9
    # no game log: both teams have full rest (3) and no fatigue flag, so only the home advantage is added
    assert abs(margin - (hp - ap_ + f.dp.HCA)) < 1e-9


def test_a_date_with_a_projections_report_is_left_alone(tmp_path):
    assert not f.has_study_report("2026-11-23", tmp_path)
    (tmp_path / "projections_2026-11-23.csv").write_text("x", encoding="utf-8")
    assert f.has_study_report("2026-11-23", tmp_path) and not f.has_study_report("2026-11-24", tmp_path)
    (tmp_path / "projections_2026-11-24_1530.csv").write_text("x", encoding="utf-8")   # the time-stamped fallback name counts too
    assert f.has_study_report("2026-11-24", tmp_path)
