"""Write the daily projections as JSON for the shared dashboard (sportsdata).

  python scripts/export_picks.py          # (with .venv\\Scripts\\python.exe) any time after a projections run

Reads docs/daily/projections_<date>.csv (written twice a day by the "NBA Daily Projections" task) and the signed 2025-26
confirmation record (data/backtest/confirmation_results.json), and writes reports/daily/<date>.json, one file per day.
The numbers are the ones the projections report already shows: the v1 model's line and total against the median of the
books in that snapshot, with a lean only where the projections report raises a flag (its 1.5-point default, not tuned).
Lines are quoted for the HOME team, negative = home favoured. Each file carries the model's own record so a screen showing
the picks can show the disclaimers first. It does not fetch anything, change the model, or commit.
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY = ROOT / "docs" / "daily"
OUT = ROOT / "reports" / "daily"
RESULTS = ROOT / "data" / "backtest" / "confirmation_results.json"
SCHEMA_VERSION = 1
FLAG_THRESHOLD = 1.5          # points; the projections report's default, as stated in its header
SPREAD_BAR = 0.5              # points of closing-line value the signed pre-registration required for spreads


def num(x):
    x = (x or "").strip()
    return float(x) if x else None


def line_text(x):
    """+4.5, -3.0, +0.75: a signed line without needless decimals."""
    t = f"{x:+.2f}".rstrip("0")
    return t + "0" if t.endswith(".") else t


def split_game(game):
    """'MIL @ WAS' -> ('MIL', 'WAS') as (away, home)."""
    away, home = (s.strip() for s in game.split("@"))
    return away, home


def spread_lean(flag, home, away, market):
    if flag == "HOME":
        return f"Lean {home} {line_text(market)}"
    if flag == "AWAY":
        return f"Lean {away} {line_text(-market)}" if market else f"Lean {away} PK"
    return ""


def total_lean(flag):
    return {"OVER": "Lean Over", "UNDER": "Lean Under"}.get(flag, "")


def build_game(row):
    away, home = split_game(row["game"])
    model_margin, market = num(row["model_home_margin"]), num(row["consensus_home_spread"])
    model_total, market_total = num(row["model_total"]), num(row["consensus_total"])
    model_spread = None if model_margin is None else -model_margin + 0.0     # home line: negative = home favoured
    return {
        "away_team": away, "home_team": home, "tip_et": datetime.strptime(row["tip_et"].strip(), "%I:%M %p").strftime("%H:%M"),
        "model_home_spread": model_spread, "market_home_spread": market,
        "gap": None if model_spread is None or market is None else round(model_spread - market, 3),
        "lean": spread_lean(row.get("spread_flag", ""), home, away, market) if market is not None else "",
        "model_total": model_total, "market_total": market_total,
        "total_gap": None if model_total is None or market_total is None else round(model_total - market_total, 3),
        "total_lean": total_lean(row.get("total_flag", "")),
        "n_books": int(row["n_books"]) if row.get("n_books") else None, "spread_range": row.get("spread_range", ""),
        "total_range": row.get("total_range", ""), "best_bettable_spread": row.get("best_bettable_spread", ""),
        "best_bettable_total": row.get("best_bettable_total", ""), "injury_report_out": row.get("injury_report_out", ""),
    }


def _win(text):
    """'240/485 = 0.4948' -> 0.4948"""
    return float(text.split("=")[1])


def disclaimers(res):
    t1, t2, sec = res["T1 spread"], res["T2 total"], res["secondary"]
    spread = (f"**NOT A RECOMMENDATION. The v1 model has no demonstrated edge.** It failed its signed 2025-26 confirmation "
              f"test. Closing-line value on spreads was {t1['mean_clv']:+.2f} points against the pre-registered "
              f"+{SPREAD_BAR:.1f} bar (permutation p = {t1['perm_p']:.4f}: a real but small effect), and on totals "
              f"{t2['mean_clv']:+.2f} points (p = {t2['perm_p']:.2f}). Settled against the closing line, its spread picks "
              f"won {100 * _win(sec['spread']['close_win']):.1f}% and its totals picks "
              f"{100 * _win(sec['total']['close_win']):.1f}%. Its average error was {sec['model MAE vs actual margin']:.1f} "
              f"points against the market close's {sec['market close MAE']:.1f}. This page only shows the model next to the "
              f"market. Early in the season its ratings are almost entirely last season's, and it does not use injuries. "
              f"The market line is the median across books, which can fall between two numbers nobody offers.")
    total = (f"**TOTALS: NOT A RECOMMENDATION.** The totals model's closing-line value in the signed confirmation was "
             f"{t2['mean_clv']:+.2f} points (95% interval {t2['ci95'][0]:+.2f} to {t2['ci95'][1]:+.2f}, p = "
             f"{t2['perm_p']:.2f}), which is not distinguishable from zero. The pattern seen in discovery did not replicate. "
             f"**There is no demonstrated totals edge.**")
    return {"product": spread, "totals": total}


def model_status(res):
    t1, t2, sec = res["T1 spread"], res["T2 total"], res["secondary"]
    return [
        {"component": "Spread", "status": f"No edge: closing-line value {t1['mean_clv']:+.2f} pts vs the +{SPREAD_BAR:.1f} bar; "
                                           f"{100 * _win(sec['spread']['close_win']):.1f}% against the close (2025-26, run once)"},
        {"component": "Totals", "status": f"No edge: closing-line value {t2['mean_clv']:+.2f} pts (p = {t2['perm_p']:.2f}); "
                                          f"{100 * _win(sec['total']['close_win']):.1f}% against the close"},
        {"component": "Injury information", "status": "Tested: the closing line already prices it (docs/Injury_v2_findings.md). "
                                                       "Shown for information; the model does not use it"},
        {"component": "Live study", "status": "Phase A (exploration) runs to 2026-12-15; the pre-registered Phase B starts "
                                               "2026-12-16 (docs/Live_Study_Plan.md)"},
    ]


def build_report(date, rows, res, mtime=None):
    games = [build_game(r) for r in rows]
    snap = next((r["snapshot_utc"] for r in rows if r.get("snapshot_utc")), None)
    if snap:
        as_of = datetime.fromisoformat(snap.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    else:
        as_of = mtime or datetime.now()
    return {
        "schema_version": SCHEMA_VERSION, "source": "export_picks", "date": date,
        "snapshot_utc": snap, "as_of_local": as_of.isoformat(timespec="seconds"), "flag_threshold": FLAG_THRESHOLD,
        "games": games, "disclaimers": disclaimers(res), "model_status": model_status(res),
    }


def csv_by_date(daily_dir):
    """{date: newest projections CSV for that date}; the timestamped fallback files count too."""
    best = {}
    for p in Path(daily_dir).glob("projections_*.csv"):
        m = re.match(r"projections_(\d{4}-\d{2}-\d{2})", p.name)
        if m and (m.group(1) not in best or p.stat().st_mtime > best[m.group(1)].stat().st_mtime):
            best[m.group(1)] = p
    return best


def main():
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for date, path in sorted(csv_by_date(DAILY).items()):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if r.get("game")]
        if not rows:
            continue
        report = build_report(date, rows, res, datetime.fromtimestamp(path.stat().st_mtime))
        (OUT / f"{date}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        written.append((date, len(rows), sum(1 for g in report["games"] if g["lean"] or g["total_lean"])))
    for date, n, leans in written:
        print(f"wrote reports/daily/{date}.json: {n} games, {leans} with a lean")
    return written


if __name__ == "__main__":
    main()
