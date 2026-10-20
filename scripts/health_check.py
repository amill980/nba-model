"""Daily health check of the live data collection. Counts only: never looks at outcomes or CLV.

Checks: odds polls today, credits remaining, injury PDFs/parse health, latest fetched game date, scheduled-task
last results. Writes data/health/health_<ET date>.txt and exits 1 if any flag is raised.
Usage: python scripts/health_check.py [--date YYYY-MM-DD]
"""
import argparse, csv, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")


def powershell_tasks():
    cmd = ("Get-ScheduledTask | Where-Object TaskName -like 'NBA*' | ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
           "'{0}|{1}|{2}' -f $_.TaskName, $i.LastTaskResult, $i.LastRunTime }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60).stdout
        return [l.split("|") for l in out.strip().splitlines() if "|" in l]
    except Exception as e:
        return [["(could not read scheduled tasks)", repr(e), ""]]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", default=datetime.now(ET).strftime("%Y-%m-%d"))
    a = ap.parse_args(); day = a.date
    lines, flags = [f"Health check for {day} (ET), run {datetime.now(ET):%Y-%m-%d %H:%M}"], []

    # odds
    raw = sorted((ROOT / "data/odds/raw").glob("*.json"))
    today = [f for f in raw if datetime.strptime(f.stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(ET).strftime("%Y-%m-%d") == day]
    arch = ROOT / "data/odds/odds_archive.csv"
    games_today = 0
    if arch.exists():
        ad = pd.read_csv(arch, usecols=["game_date_et", "event_id"]).drop_duplicates()
        games_today = int((ad.game_date_et == day).sum())
    lines.append(f"Odds: {len(today)} snapshots today ({', '.join(datetime.strptime(f.stem, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).astimezone(ET).strftime('%H:%M') for f in today)}); games seen in archive today: {games_today}")
    # scheduled-slot coverage: which of the day's planned polls produced a snapshot (gaps are accepted but recorded)
    SLOTS = ["11:00", "13:30", "16:00", "18:30", "20:30", "22:00"]
    snap_times = [datetime.strptime(f.stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(ET) for f in today]
    commences = []
    if arch.exists():
        cm = pd.read_csv(arch, usecols=["game_date_et", "commence_time_utc"]).drop_duplicates()
        commences = [pd.Timestamp(c).tz_convert(ET).to_pydatetime() for c in cm[cm.game_date_et == day].commence_time_utc]
    now_et = datetime.now(ET); d0 = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ET)
    gap_rows, missed = [], []
    for sl in SLOTS:
        hh, mm = map(int, sl.split(":")); t_slot = d0.replace(hour=hh, minute=mm)
        if not commences or t_slot > now_et or not any(c >= t_slot for c in commences): continue   # not expected / not due yet
        hit = [t for t in snap_times if t_slot - timedelta(minutes=5) <= t <= t_slot + timedelta(minutes=60)]
        status = "ok" if hit and min(hit) <= t_slot + timedelta(minutes=15) else ("late" if hit else "MISSED")
        gap_rows.append((day, sl, status, min(hit).strftime("%H:%M") if hit else ""))
        if status == "MISSED": missed.append(sl)
    lines.append("Poll slots: " + (", ".join(f"{sl}={st}" + (f"@{at}" if at else "") for _, sl, st, at in gap_rows) if gap_rows else "none due"))
    if missed: flags.append("missed odds polls (accepted gap, recorded): " + ", ".join(missed))
    if gap_rows:
        gp = ROOT / "data/health/poll_gaps.csv"; gp.parent.mkdir(parents=True, exist_ok=True)
        old = pd.read_csv(gp) if gp.exists() else pd.DataFrame(columns=["date", "slot", "status", "snapshot_at"])
        new = pd.DataFrame(gap_rows, columns=["date", "slot", "status", "snapshot_at"])
        pd.concat([old[old.date != day], new]).to_csv(gp, index=False)
    q = ROOT / "data/odds/quota_log.csv"
    if q.exists():
        last = list(csv.DictReader(q.open(newline="")))[-1]
        lines.append(f"Credits remaining at last poll: {last['credits_remaining']} (log time {last['captured_utc']})")
        if last["credits_remaining"] and int(last["credits_remaining"]) < 150: flags.append("odds credits below 150")

    # injuries
    pdfs = sorted((ROOT / "data/injuries/raw").glob("*.pdf"))
    ymd = day.replace("-", "_") if False else day
    todays = [p for p in pdfs if f"_{day}_" in p.name]
    lines.append(f"Injury PDFs: {len(pdfs)} total, {len(todays)} dated today; newest {pdfs[-1].name if pdfs else 'none'}")
    if not todays: flags.append("no injury PDFs dated today")
    st = ROOT / "data/injuries/injury_status.csv"
    if st.exists():
        d = pd.read_csv(st)
        bad = int((~d.apply(lambda r: isinstance(r.matchup, str) and isinstance(r.team, str) and r.team in r.matchup.split("@"), axis=1)).sum()) if len(d) else 0
        unparsed = (ROOT / "data/injuries/unparsed_sample.txt").read_text().count("\n") if (ROOT / "data/injuries/unparsed_sample.txt").exists() else 0
        real = d[d.status != "NOT_YET_SUBMITTED"]
        lines.append(f"Parsed injury rows: {len(d)} ({len(real)} with a player status); rows with team not in matchup: {bad}")
        if bad: flags.append("parser rows with team not in matchup")
        pe = ROOT / "data/injuries/parse_errors.txt"
        if pe.exists() and pe.read_text().strip(): lines.append("Parse errors pending retry: " + str(len(pe.read_text().strip().splitlines())))
        if todays and len(pdfs) and not len(d): flags.append("PDFs present but nothing parsed")
    # results
    g = ROOT / "data/games/team_games_2026-27_Regular_Season.csv"
    if g.exists() and g.stat().st_size > 5:
        gl = pd.read_csv(g); lines.append(f"Game log 2026-27: {gl.GAME_ID.nunique()} games, latest {gl.GAME_DATE.max()}")
    else:
        lines.append("Game log 2026-27: no games yet")
    # tasks
    for name, res, when in powershell_tasks():
        ok = name == "NBA Health Check" or res.strip() in ("0", "267011", "267009", "267014")  # 0 ok; 267011 never run; 267009 running; 267014 stopped by system (sleep)
        lines.append(f"Task {name}: last result {res.strip()} at {when.strip()}" + ("" if ok else "  <-- FLAG"))
        if not ok: flags.append(f"task {name} last result {res.strip()}")
    lines.append("FLAGS: " + ("none" if not flags else "; ".join(flags)))
    out = ROOT / "data/health"; out.mkdir(parents=True, exist_ok=True)
    (out / f"health_{day}.txt").write_text("\n".join(lines))
    print("\n".join(lines)); raise SystemExit(1 if flags else 0)


if __name__ == "__main__":
    main()
