"""Synthetic checks for profile selection and rosters. Run: python tests/test_profiles.py"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_profiles as bp, fetch_rosters as fr

def rows(pid, name, team, n, minutes, pts=20, start=1):
    return [dict(PLAYER_ID=pid, PLAYER_NAME=name, TEAM_ABBREVIATION=team, GAME_ID=f"g{start+i}", GAME_DATE=f"2026-11-{start+i:02d}", MIN=minutes, PTS=pts, REB=5, AST=4, STL=1, BLK=0, TOV=2,
                 FGM=8, FGA=16, FG3M=2, FG3A=6, FTM=2, FTA=4) for i in range(n)]
logs = pd.DataFrame(rows(1, "Sam Star", "AAA", 10, 30.0) + rows(2, "Bench Guy", "AAA", 10, 10.0) + rows(3, "New Guy", "AAA", 3, 25.0, start=8))
tg = pd.DataFrame([dict(TEAM_ABBREVIATION="AAA", GAME_ID=f"g{i}") for i in range(1, 13)])
roster = pd.DataFrame([dict(PLAYER_ID=1, PLAYER="Sam Star", TEAM="AAA", POSITION="G", HEIGHT="6-5", HEIGHT_IN=77, WEIGHT="200", AGE=25.0, EXP="4", SCHOOL="X", HOW_ACQUIRED="draft")])
inj = pd.DataFrame([dict(player="Star,Sam", status="Questionable", game_date="11/12/2026", reason_on_line="Injury/Illness-Knee", report_time_et="11/11/26 05:00 PM"),
                    dict(player="Star,Sam", status="Out", game_date="11/05/2026", reason_on_line="Injury/Illness-Ankle", report_time_et="11/04/26 05:00 PM")])
df = bp.build(logs, pd.DataFrame(), roster, tg, inj, min_mpg=15, min_gp=5)
assert list(df.player) == ["Sam Star"], df.player.tolist()                 # bench (10 mpg) and new guy (3 games) excluded
r = df.iloc[0]
assert abs(r.pts_per36 - 24.0) < 1e-9 and abs(r.mpg - 30) < 1e-9           # 20 pts in 30 min = 24 per 36
assert r.games_missed == 2 and r.team_games == 12                          # team played 12, he played 10
assert r.latest_injury_status == "Questionable" and r.times_listed_out_or_doubtful == 1
assert abs(r.ts_pct - 20 / (2 * (16 + 0.44 * 4))) < 1e-9
assert r.position == "G" and r.height_in == 77
df2 = bp.build(logs, pd.DataFrame(), roster, tg, inj, min_mpg=9, min_gp=5)
assert set(df2.player) == {"Sam Star", "Bench Guy"}                        # lower threshold adds the bench player
assert df2.set_index("player").loc["Bench Guy", "latest_injury_status"] == "none on record"
old = pd.DataFrame([dict(PLAYER_ID=1, PLAYER="A", TEAM="X"), dict(PLAYER_ID=2, PLAYER="B", TEAM="X"), dict(PLAYER_ID=3, PLAYER="C", TEAM="Y")])
new = pd.DataFrame([dict(PLAYER_ID=1, PLAYER="A", TEAM="X"), dict(PLAYER_ID=3, PLAYER="C", TEAM="Z"), dict(PLAYER_ID=4, PLAYER="D", TEAM="Y")])
ch = fr.diff_rosters(old, new, "2026-11-10").set_index("player")
assert ch.loc["B", "change"] == "left roster" and ch.loc["C", "change"] == "changed team" and ch.loc["D", "change"] == "joined roster" and "A" not in ch.index
assert fr.height_inches("6-10") == 82
print("profile tests passed")
