"""Checks of the picks export: sign conventions, leans from the report's own flags, text built from the signed record.
Run: .venv\\Scripts\\python.exe tests\\test_export_picks.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import export_picks as ep  # noqa: E402

ROW = {"report_date": "2026-10-21", "tip_et": "07:00 PM", "game": "MIL @ WAS", "model_home_margin": "-3.4",
       "model_total": "234.1", "consensus_home_spread": "-4.5", "consensus_total": "239.5", "n_books": "9",
       "spread_range": "-5 to -4.5", "total_range": "239.5 to 239.5", "spread_flag": "AWAY", "total_flag": "UNDER",
       "best_bettable_spread": "bovada +5 (-105)", "best_bettable_total": "bovada 239.5 (-110)",
       "injury_report_out": "WAS X Out", "snapshot_utc": "2026-10-21T00:30:11Z"}


def results():
    return json.loads((ROOT / "data" / "backtest" / "confirmation_results.json").read_text(encoding="utf-8"))


def test_signs_and_gap():
    g = ep.build_game(ROW)
    # the model has WAS losing by 3.4, so its home line is +3.4; the market has WAS favoured by 4.5
    assert (g["away_team"], g["home_team"], g["tip_et"]) == ("MIL", "WAS", "19:00")
    assert g["model_home_spread"] == 3.4 and g["market_home_spread"] == -4.5
    assert g["gap"] == 7.9                                  # positive: the model rates the home side less than the market
    assert g["total_gap"] == -5.4
    assert g["lean"] == "Lean MIL +4.5" and g["total_lean"] == "Lean Under"


def test_home_lean_and_no_flag():
    row = dict(ROW, model_home_margin="4.3", consensus_home_spread="-1.0", spread_flag="HOME", total_flag="no flag")
    g = ep.build_game(row)
    assert g["model_home_spread"] == -4.3 and g["gap"] == -3.3
    assert g["lean"] == "Lean WAS -1.0" and g["total_lean"] == ""
    assert ep.build_game(dict(ROW, spread_flag="no flag"))["lean"] == ""


def test_pickem_and_quarter_lines():
    assert ep.spread_lean("AWAY", "WAS", "MIL", 0.0) == "Lean MIL PK"
    assert ep.line_text(4.5) == "+4.5" and ep.line_text(-3.0) == "-3.0" and ep.line_text(0.75) == "+0.75"
    assert (ep.build_game(dict(ROW, model_home_margin="0"))["model_home_spread"]) == 0.0
    assert str(ep.build_game(dict(ROW, model_home_margin="0"))["model_home_spread"]) == "0.0"      # never -0.0


def test_missing_numbers_do_not_crash():
    g = ep.build_game(dict(ROW, consensus_home_spread="", consensus_total=""))
    assert g["gap"] is None and g["total_gap"] is None and g["lean"] == ""


def test_disclaimers_quote_the_signed_record():
    res = results()
    d = ep.disclaimers(res)
    assert "no demonstrated edge" in d["product"] and "+0.35" in d["product"] and "+0.5 bar" in d["product"]
    assert "49.5%" in d["product"] and "49.4%" in d["product"] and "11.5" in d["product"] and "10.9" in d["product"]
    assert "TOTALS" in d["totals"] and "no demonstrated totals edge" in d["totals"]
    assert [m["component"] for m in ep.model_status(res)][:2] == ["Spread", "Totals"]


def test_report_and_file_selection():
    res = results()
    rep = ep.build_report("2026-10-21", [ROW], res)
    assert rep["date"] == "2026-10-21" and len(rep["games"]) == 1 and rep["snapshot_utc"] == "2026-10-21T00:30:11Z"
    assert rep["as_of_local"].startswith("2026-10-2")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "projections_2026-10-21.csv").write_text("a")
        (d / "projections_2026-10-20.csv").write_text("a")
        (d / "projections_2026-10-21_1530.csv").write_text("newer")           # timestamped fallback, written later
        (d / "latest.csv").write_text("x")
        got = ep.csv_by_date(d)
        assert sorted(got) == ["2026-10-20", "2026-10-21"] and got["2026-10-21"].name == "projections_2026-10-21_1530.csv"


if __name__ == "__main__":
    test_signs_and_gap()
    test_home_lean_and_no_flag()
    test_pickem_and_quarter_lines()
    test_missing_numbers_do_not_crash()
    test_disclaimers_quote_the_signed_record()
    test_report_and_file_selection()
    print("ALL PASS")
