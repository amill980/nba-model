"""Archive the official NBA injury report PDFs.

The league posts a time-stamped PDF every 15 minutes. Every PDF is kept (about
6 MB per day): the files embed a creation timestamp, so byte hashes always differ and
byte-level dedupe does not work. Dedupe on extracted text later, once a PDF parser
is chosen. manifest.csv records file name, report time and sha256 for each file so
the timing of every change is preserved for the "what was known when" audit.

No API key needed. Usage:  python scripts/archive_injuries.py [--page URL]
"""
import argparse, csv, hashlib, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "injuries" / "raw"
MANIFEST = ROOT / "data" / "injuries" / "manifest.csv"
DEFAULT_PAGE = "https://official.nba.com/nba-injury-report-2025-26-season/"
UA = {"User-Agent": "Mozilla/5.0"}
LINK = re.compile(r'https?://[^"\']+/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})([AP]M)\.pdf')


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=DEFAULT_PAGE)
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    seen = set()
    last_hash = None
    if MANIFEST.exists():
        with MANIFEST.open(newline="") as f:
            rows = list(csv.DictReader(f))
        seen = {r["file"] for r in rows}
        saved = [r for r in rows if r["status"] == "saved"]
        last_hash = saved[-1]["sha256"] if saved else None

    html = get(a.page).decode("utf-8", "replace")
    links = sorted({m.group(0) for m in LINK.finditer(html)},
                   key=lambda u: _sortkey(LINK.search(u)))
    new_manifest = not MANIFEST.exists()
    n_saved = n_dup = 0
    with MANIFEST.open("a", newline="") as f:
        w = csv.writer(f)
        if new_manifest:
            w.writerow(["file", "report_time_local_label", "sha256", "status"])
        for url in links:
            name = url.rsplit("/", 1)[1]
            if name in seen:
                continue
            data = get(url)
            h = hashlib.sha256(data).hexdigest()
            m = LINK.search(url)
            label = f"{m.group(1)} {m.group(2)}:{m.group(3)} {m.group(4)}"
            if h == last_hash:
                w.writerow([name, label, h, "duplicate"]); n_dup += 1
            else:
                (RAW / name).write_bytes(data)
                w.writerow([name, label, h, "saved"]); n_saved += 1
                last_hash = h
    print(f"Links on page: {len(links)}. New saved: {n_saved}, new duplicates: {n_dup}.")


def _sortkey(m):
    date, hh, mm, ap = m.groups()
    h = int(hh) % 12 + (12 if ap == "PM" else 0)
    return (date, h, int(mm))


if __name__ == "__main__":
    main()
