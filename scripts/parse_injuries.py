"""Parse archived NBA injury report PDFs into one tidy table.

Output: data/injuries/injury_status.csv
  report_time_et, file, game_date, game_time_et, matchup, team, player, status, reason_on_line
status is one of Out, Doubtful, Questionable, Probable, Available, NOT_YET_SUBMITTED.
Reason cells span several lines and the PDF puts fragments before AND after the player line, so only the
text on the player's own line is kept (reason_on_line, may be partial). Status is exact.
Unparsed lines (reason fragments, etc.) are counted and the first ones written to data/injuries/unparsed_sample.txt
so a human can check that nothing important is being dropped.

Incremental: files already in data/injuries/parsed_files.txt are skipped. Usage:
  python scripts/parse_injuries.py [--dir data/injuries/raw] [--rebuild]
"""
import argparse, re, csv
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
INJ = ROOT / "data" / "injuries"
TEAMS = {  # no-space names as printed in the report -> abbreviation
    "AtlantaHawks": "ATL", "BostonCeltics": "BOS", "BrooklynNets": "BKN", "CharlotteHornets": "CHA", "ChicagoBulls": "CHI",
    "ClevelandCavaliers": "CLE", "DallasMavericks": "DAL", "DenverNuggets": "DEN", "DetroitPistons": "DET",
    "GoldenStateWarriors": "GSW", "HoustonRockets": "HOU", "IndianaPacers": "IND", "LAClippers": "LAC",
    "LosAngelesClippers": "LAC", "LosAngelesLakers": "LAL", "LALakers": "LAL", "MemphisGrizzlies": "MEM", "MiamiHeat": "MIA",
    "MilwaukeeBucks": "MIL", "MinnesotaTimberwolves": "MIN", "NewOrleansPelicans": "NOP", "NewYorkKnicks": "NYK",
    "OklahomaCityThunder": "OKC", "OrlandoMagic": "ORL", "Philadelphia76ers": "PHI", "PhoenixSuns": "PHX",
    "PortlandTrailBlazers": "POR", "SacramentoKings": "SAC", "SanAntonioSpurs": "SAS", "TorontoRaptors": "TOR",
    "UtahJazz": "UTA", "WashingtonWizards": "WAS"}
STATUS = r"(Out|Doubtful|Questionable|Probable|Available)"
RE_HDR = re.compile(r"^Injury Report:\s+(\d\d/\d\d/\d\d)\s+(\d\d:\d\d [AP]M)")
RE_DATE = re.compile(r"^(\d\d/\d\d/\d{4})\s+")
RE_TIME = re.compile(r"^(\d\d:\d\d)\(ET\)\s+([A-Z]{2,3}@[A-Z]{2,3})\s*")
RE_MATCH = re.compile(r"^([A-Z]{2,3}@[A-Z]{2,3})\s+")
RE_PLAYER = re.compile(rf"^([^\s,]+,[^\s]+)\s+{STATUS}\b\s*(.*)$")
RE_NYS = re.compile(r"^NOTYETSUBMITTED\b")
FIELDS = ["report_time_et", "file", "game_date", "game_time_et", "matchup", "team", "player", "status", "reason_on_line"]


def parse_pdf(path):
    rows, unparsed = [], []
    rep_time = None; gdate = gtime = matchup = team = None
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for raw in (pg.extract_text() or "").split("\n"):
                line = raw.strip()
                if not line or line.startswith("GameDate GameTime") or re.match(r"^Page\d+of\d+", line):
                    continue
                m = RE_HDR.match(line)
                if m:
                    rep_time = f"{m.group(1)} {m.group(2)}"; continue
                m = RE_DATE.match(line)
                if m: gdate = m.group(1); line = line[m.end():]
                m = RE_TIME.match(line)
                if m: gtime, matchup = m.group(1), m.group(2); line = line[m.end():]
                else:
                    m = RE_MATCH.match(line)
                    if m: matchup = m.group(1); line = line[m.end():]   # same tip time as the game above
                first = line.split(" ", 1)[0] if line else ""
                if first in TEAMS:
                    team = TEAMS[first]; line = line[len(first):].strip()
                if RE_NYS.match(line):
                    rows.append([rep_time, path.name, gdate, gtime, matchup, team, "", "NOT_YET_SUBMITTED", ""]); continue
                m = RE_PLAYER.match(line)
                if m:
                    rows.append([rep_time, path.name, gdate, gtime, matchup, team, m.group(1), m.group(2), m.group(3)]); continue
                if line:
                    unparsed.append(line)
    return rows, unparsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(INJ / "raw")); ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--out", default=str(INJ / "injury_status.csv"))
    a = ap.parse_args()
    out = Path(a.out); done_f = INJ / "parsed_files.txt"
    done = set() if a.rebuild or not done_f.exists() else set(done_f.read_text().split())
    if a.rebuild and out.exists(): out.unlink()
    files = [f for f in sorted(Path(a.dir).glob("*.pdf")) if f.name not in done]
    new_out = not out.exists(); n_rows = n_un = 0; samples = []; errors = []
    with out.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new_out: w.writerow(FIELDS)
        for f in files:
            try:
                rows, un = parse_pdf(f)
            except Exception as e:   # partial download or unreadable PDF: skip now, retry next run (not marked done)
                errors.append(f"{f.name}: {e!r}"); continue
            w.writerows(rows); n_rows += len(rows); n_un += len(un)
            samples += [f"{f.name}: {u}" for u in un[:20]]; done.add(f.name)
    done_f.write_text("\n".join(sorted(done)))
    (INJ / "unparsed_sample.txt").write_text("\n".join(samples[:400]))
    bad = 0
    import pandas as pd
    df = pd.read_csv(out) if out.exists() else pd.DataFrame()
    if len(df):
        bad = int((~df.apply(lambda r: isinstance(r.matchup, str) and isinstance(r.team, str) and r.team in r.matchup.split("@"), axis=1)).sum())
    print(f"parsed {len(files)} files: {n_rows} status rows, {n_un} unparsed lines (see unparsed_sample.txt); rows whose team is not in the matchup: {bad}; files that failed to parse (will retry): {len(errors)}")


if __name__ == "__main__":
    main()
