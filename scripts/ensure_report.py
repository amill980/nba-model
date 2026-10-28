"""Self-healing for the daily report. Run every ~10 minutes from noon: if today's projections report does not exist yet
(the noon task was killed by sleep, the odds poll failed at wake, ...), build it now. Does nothing once the report exists
or on a day with no games. Usage: python scripts/ensure_report.py
"""
import subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs" / "daily"


def should_run(now, report_exists, nogames_stamp, start_hour=12):
    """Pure decision: build only after the start hour, only if no report yet, and not on a day known to have no games."""
    return now.hour >= start_hour and not report_exists and not nogames_stamp


def main():
    now = datetime.now(ZoneInfo("America/New_York")); day = now.strftime("%Y-%m-%d")
    report, stamp = D / f"projections_{day}.md", D / f".nogames_{day}"
    if not should_run(now, report.exists(), stamp.exists()):
        return 0
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "daily_projections.py"), "--today"], capture_output=True, text=True)
    out = (r.stdout + r.stderr)
    if report.exists():
        print(f"report built for {day}")
    elif "No odds in the archive" in out or "No pregame odds" in out:
        D.mkdir(parents=True, exist_ok=True); stamp.write_text("no games / no odds today")
        print(f"no games today ({day}); not trying again")
    else:
        print("report not built:", out.strip()[-300:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
