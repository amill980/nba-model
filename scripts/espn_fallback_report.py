"""Site-only fallback: a daily report for the website when The Odds API gave no lines, using ESPN's own line instead.

  python scripts/espn_fallback_report.py [--date YYYY-MM-DD]      (default: today, Eastern)

Why: the daily projections report (daily_projections.py) stops with "No odds in the archive" when the Odds API key has no
credits left, so no report reaches the site. ESPN's public scoreboard and odds endpoints list each game's current line (one
or two books, free, no credits). This script writes reports/daily/<date>.json in the same shape export_picks.py writes, with
the model's line next to ESPN's, for the games that have not tipped.

What it never does: it does not touch the live study. It writes nothing for a date that already has a projections report in
docs/daily (the study's own output), it does not read or write the odds archive or any snapshot file, and it never replaces
a report that has market lines. The model is the frozen v1, computed with daily_projections.py's own ratings and rest
functions and the same formula; no leans are shown, because a lean off one book is not the median-across-books rule the
projections report uses. n_books is the number of ESPN providers behind the line (usually 1).
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import daily_projections as dp          # noqa: E402  (ratings, rest_info and the frozen v1 constants; importing runs nothing)
import export_picks as ep               # noqa: E402  (the report's shape and its disclaimers)

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "fairline-nba-logs/1.0"}
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={ymd}&limit=500"
ODDS = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{eid}/competitions/{eid}/odds"
ALIAS = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
NOTE = (" For games where The Odds API had no line, the market line is ESPN's own current line, usually from one book, "
        "and n_books says how many.")


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception:               # noqa: BLE001 - a hiccup must not cost the report
            time.sleep(1 + i)
    return None


def num(s):
    """'+2.5' -> 2.5, '-110' -> -110.0, 'PK'/'EVEN' -> 0.0, anything else -> None."""
    if s is None:
        return None
    t = str(s).strip().upper()
    if t in ("PK", "PICK", "PICKEM", "EVEN"):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return None


def current_lines(payload):
    """[(provider, home_spread, total)] from ESPN's odds payload: current lines only, in-play providers dropped. The
    home spread is in book notation (negative = home favoured), as everywhere in this project."""
    out = []
    for it in (payload or {}).get("items", []):
        name = (it.get("provider") or {}).get("name") or ""
        if "live" in name.lower():
            continue
        home = (it.get("homeTeamOdds") or {}).get("current") or {}
        spread = num(((home.get("pointSpread") or {}).get("american")))
        total = num((((it.get("current") or {}).get("total")) or {}).get("alternateDisplayValue"))
        if spread is None and total is None:
            continue
        out.append((name, spread, total))
    return out


def market(lines):
    """(spread, total, n_books): the median over the providers, None where none gave one."""
    sp = [s for _, s, _ in lines if s is not None]
    tt = [t for _, _, t in lines if t is not None]
    return (float(median(sp)) if sp else None, float(median(tt)) if tt else None, max(len(sp), len(tt)))


def model_line(R, lg, gc, home, away, day):
    """The frozen v1 model for one game, exactly as daily_projections.py computes it: (home margin, total)."""
    h, w = R.loc[home], R.loc[away]
    pace = (h.bp + w.bp) / 2
    hp = pace * (h.bo + w.bd - lg) / 100
    ap_ = pace * (w.bo + h.bd - lg) / 100
    hr, hf = dp.rest_info(gc, home, day)
    ar, af = dp.rest_info(gc, away, day)
    margin = hp - ap_ + dp.HCA + dp.REST_COEF * np.clip(hr - ar, -dp.REST_CAP, dp.REST_CAP) + (hf - af) * dp.FATIGUE
    return float(margin), float(hp + ap_)


def has_study_report(day, daily_dir):
    return any(Path(daily_dir).glob(f"projections_{day}*.csv"))


def build_rows(day, events, odds_by_event, R, lg, gc, now):
    """Report rows in the shape export_picks.build_game reads, for games that have not tipped and have an ESPN line."""
    rows = []
    for e in events:
        c = e["competitions"][0]
        if e["status"]["type"]["state"] != "pre":
            continue
        tip = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        if tip <= now:
            continue
        t = {x["homeAway"]: ALIAS.get(x["team"]["abbreviation"], x["team"]["abbreviation"]) for x in c["competitors"]}
        home, away = t.get("home"), t.get("away")
        if home not in R.index or away not in R.index:
            continue
        spread, total, n = market(odds_by_event.get(e["id"], []))
        if spread is None and total is None:
            continue
        margin, mtotal = model_line(R, lg, gc, home, away, day)
        rows.append({
            "game": f"{away} @ {home}", "tip_et": tip.astimezone(ET).strftime("%I:%M %p"),
            "model_home_margin": f"{margin:.1f}", "model_total": f"{mtotal:.1f}",
            "consensus_home_spread": "" if spread is None else f"{spread:g}", "consensus_total": "" if total is None else f"{total:g}",
            "n_books": str(n), "spread_flag": "", "total_flag": "", "snapshot_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return sorted(rows, key=lambda r: datetime.strptime(r["tip_et"], "%I:%M %p"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(ET).strftime("%Y-%m-%d"))
    ap.add_argument("--daily", default=str(ROOT / "docs" / "daily"))
    ap.add_argument("--out", default=str(ep.OUT))
    a = ap.parse_args()
    day = a.date
    if has_study_report(day, a.daily):
        print(f"{day}: the projections report exists; nothing to fill")
        return 0
    sb = get(SCOREBOARD.format(ymd=day.replace("-", "")))
    events = (sb or {}).get("events", [])
    if not events:
        print(f"{day}: no games on ESPN's scoreboard (or it did not answer)")
        return 0
    odds = {e["id"]: current_lines(get(ODDS.format(eid=e["id"]))) for e in events if e["status"]["type"]["state"] == "pre"}
    R, lg, gc = dp.ratings()
    now = datetime.now(timezone.utc)
    rows = build_rows(day, events, odds, R, lg, gc, now)
    if not rows:
        print(f"{day}: no game has an ESPN line yet; nothing written")
        return 0
    res = json.loads(ep.RESULTS.read_text(encoding="utf-8"))
    report = ep.build_report(day, rows, res, datetime.now())
    report["disclaimers"]["product"] += NOTE
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{day}.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if any(g.get("market_home_spread") is not None for g in old.get("games", [])) and old.get("source") != "espn_fallback":
            print(f"{day}: a report with market lines is already there; kept")
            return 0
    report["source"] = "espn_fallback"
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path}: {len(rows)} games with an ESPN line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
