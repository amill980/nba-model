"""Move the NBA cloud run's persistent files between the `state` branch checkout and the working tree.

The GitHub Actions run (.github/workflows/nba-daily.yml) starts from a clean checkout, so everything it must remember lives on the orphan
`state` branch of this repository, checked out into `_state/`. (It cannot be checked out into `data/` the way the college basketball job does,
because a few files under `data/` are tracked on main.) Layout of the state branch, and where each part goes in the working tree:

    games/*.csv            -> data/games/               team game logs: earlier seasons from nba_api, this season built from ESPN
    odds_history/...       -> data/odds_history/        the sportsdata history file the unified tables are built from (static)
    espn_odds/days/*.csv   -> data/espn_odds/days/      ESPN BET open/close lines for earlier seasons (static)
    odds/quota_log.csv     -> data/odds/quota_log.csv   the Odds API credit log, so the "stop below the reserve" guard keeps its memory
    odds/raw/*.json        -> data/odds/raw/            the last few days of odds snapshots (older ones are dropped)
    daily_reports/*.json   -> reports/daily/            every earlier day's report; reports/daily is not reliably tracked, and the site's picks file
                                                         is rebuilt from all of them

`restore` copies state into the tree (and makes sure the odds table exists, because daily_projections.py crashes without one). `save` copies
back what a run changes: this season's game log, the quota log, new snapshots and the daily reports. Nothing here touches the model.

Usage: python scripts/cloud_state.py restore|save --state _state [--keep-raw-days 3]
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_HEADER = "captured_utc,event_id,commence_time_utc,game_date_et,home,away,book,market,last_update_utc,outcome,price,point,pregame\n"

# (state subfolder, working-tree folder, glob of the files it holds, whether `save` writes it back)
PARTS = [
    ("games", "data/games", "*.csv", True),
    ("odds_history", "data/odds_history", "**/*.csv", False),
    ("espn_odds/days", "data/espn_odds/days", "*.csv", False),
    ("odds/raw", "data/odds/raw", "*.json", True),
    ("daily_reports", "reports/daily", "*.json", True),
]
QUOTA = ("odds/quota_log.csv", "data/odds/quota_log.csv")


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src_dir: Path, dst_dir: Path, pattern: str) -> int:
    """Copy the files under `src_dir` that match `pattern` to the same relative paths under `dst_dir`, overwriting. Returns how many."""
    n = 0
    for f in sorted(src_dir.glob(pattern)) if src_dir.is_dir() else []:
        if f.is_file():
            _copy(f, dst_dir / f.relative_to(src_dir))
            n += 1
    return n


def ensure_odds_table(root: Path) -> None:
    """daily_projections.py reads data/odds/odds_archive.csv unconditionally; on a first run (no snapshot yet) give it a valid empty table."""
    table = root / "data" / "odds" / "odds_archive.csv"
    (root / "data" / "odds" / "raw").mkdir(parents=True, exist_ok=True)
    if not table.exists():
        table.write_text(ARCHIVE_HEADER, encoding="utf-8")


def restore(state: Path, root: Path = ROOT) -> dict:
    counts = {sub: copy_tree(state / sub, root / tree, pattern) for sub, tree, pattern, _ in PARTS}
    if (state / QUOTA[0]).is_file():
        _copy(state / QUOTA[0], root / QUOTA[1])
        counts["odds/quota_log.csv"] = 1
    ensure_odds_table(root)
    return counts


def save(state: Path, root: Path = ROOT, keep_raw_days: float = 3, now: float | None = None) -> dict:
    """Copy this run's changes into `state`. Raw odds snapshots older than `keep_raw_days` are removed from the state, so it does not grow."""
    now = now or time.time()
    counts = {}
    for sub, tree, pattern, writable in PARTS:
        if writable:
            counts[sub] = copy_tree(root / tree, state / sub, pattern)
    if (root / QUOTA[1]).is_file():
        _copy(root / QUOTA[1], state / QUOTA[0])
    removed = 0
    for f in (state / "odds" / "raw").glob("*.json") if (state / "odds" / "raw").is_dir() else []:
        if now - f.stat().st_mtime > keep_raw_days * 86400:
            f.unlink()
            removed += 1
    counts["old snapshots removed"] = removed
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["restore", "save"])
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--keep-raw-days", type=float, default=3)
    a = ap.parse_args(argv)
    counts = restore(a.state) if a.action == "restore" else save(a.state, keep_raw_days=a.keep_raw_days)
    print(f"{a.action}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
