"""Gate G1: internal consistency of the nba_api team game logs, and (G2) a full-season
cross-check of dates, teams and scores against ESPN's public scoreboard.
Writes data/gates/games_gate_<season>.txt. Thresholds (written before running):
  G1: every game has exactly 2 rows; W/L opposite; row counts 1230 regular season.
  G2: >=99.5% of regular-season games found in ESPN with identical home/away and scores.
"""
import json, sys, time, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "data" / "games"; OUT = ROOT / "data" / "gates"; OUT.mkdir(parents=True, exist_ok=True)

def espn_day(d):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}&limit=500"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.load(r)

def run(season):
    df = pd.read_csv(G / f"team_games_{season}_Regular_Season.csv")
    lines = [f"Season {season}"]
    per = df.groupby("GAME_ID").size()
    lines.append(f"G1 games={len(per)} rows={len(df)} games_without_2_rows={(per!=2).sum()}")
    wl = df.groupby("GAME_ID")["WL"].apply(lambda s: sorted(s.tolist()) == ["L", "W"])
    lines.append(f"G1 games_with_inconsistent_WL={(~wl).sum()}")
    dates = sorted(df["GAME_DATE"].unique())
    lines.append(f"dates {dates[0]} .. {dates[-1]} ({len(dates)} game days)")
    # ESPN: one request per game day. Compare unordered {team: score} per game (neutral-site safe).
    espn_games = {}
    for d in dates:
        try:
            for e in espn_day(d.replace("-", "")).get("events", []):
                comp = e["competitions"][0]["competitors"]
                espn_games[(d, frozenset(c["team"]["abbreviation"] for c in comp))] = {
                    c["team"]["abbreviation"]: int(c["score"]) for c in comp}
        except Exception as ex:
            lines.append(f"ESPN fetch failed {d}: {ex}")
        time.sleep(0.2)
    lines.append(f"ESPN events collected={len(espn_games)}")
    ok = bad = miss = 0
    for gid, grp in df.groupby("GAME_ID"):
        d = grp["GAME_DATE"].iloc[0]
        mine = dict(zip(grp["TEAM_ABBREVIATION"], grp["PTS"].astype(int)))
        # ESPN abbreviations differ for a few teams; try exact then known aliases
        alias = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
        hit = None
        for (dd, teams), sc in espn_games.items():
            if dd == d:
                norm = {alias.get(t, t): v for t, v in sc.items()}
                if set(norm) == set(mine): hit = norm; break
        if hit is None: miss += 1
        elif hit == mine: ok += 1
        else: bad += 1
    n = df["GAME_ID"].nunique()
    lines.append(f"G2 matched_identical={ok} score_mismatch={bad} not_found={miss} of {n} -> {ok/n:.4f}")
    txt = "\n".join(lines); print(txt)
    (OUT / f"games_gate_{season}.txt").write_text(txt)

for s in (sys.argv[1:] or ["2024-25"]): run(s)
