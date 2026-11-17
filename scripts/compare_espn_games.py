"""Compare ESPN-sourced team game logs with the nba_api file, game by game and figure by figure.

Usage: python scripts/compare_espn_games.py <nba_api csv> <espn csv>

Rows are matched on (GAME_DATE, TEAM_ABBREVIATION), because the two files use different game ids. Every box-score figure the ratings or the
exports could read is compared exactly; the ids (SEASON_ID, TEAM_ID, GAME_ID) and VIDEO_AVAILABLE are not. Exit code 0 only if both files hold the
same team-games and every figure matches. Read-only: nothing is written.
"""
import sys

import pandas as pd

KEY = ["GAME_DATE", "TEAM_ABBREVIATION"]
FIGURES = ["TEAM_NAME", "MATCHUP", "WL", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS"]


def compare(nba: pd.DataFrame, espn: pd.DataFrame) -> dict:
    """{'only_nba': keys, 'only_espn': keys, 'mismatches': {column: [(key, nba, espn), ...]}, 'compared': n}."""
    a = nba.drop_duplicates(KEY).set_index(KEY)
    b = espn.drop_duplicates(KEY).set_index(KEY)
    both = a.index.intersection(b.index)
    mism = {}
    for col in FIGURES:
        x, y = a.loc[both, col], b.loc[both, col]
        if x.dtype.kind in "fc" or y.dtype.kind in "fc":
            bad = ~((x.astype(float) - y.astype(float)).abs() < 1e-9)
        else:
            bad = x.astype(str) != y.astype(str)
        if bad.any():
            mism[col] = [(k, x[k], y[k]) for k in x.index[bad]]
    return {"only_nba": sorted(a.index.difference(b.index)), "only_espn": sorted(b.index.difference(a.index)), "mismatches": mism, "compared": len(both)}


def main(argv=None) -> int:
    nba_path, espn_path = (argv or sys.argv[1:])[:2]
    nba, espn = pd.read_csv(nba_path, dtype={"GAME_ID": str}), pd.read_csv(espn_path, dtype={"GAME_ID": str})
    r = compare(nba, espn)
    print(f"nba_api file: {len(nba)} team-games | ESPN file: {len(espn)} team-games | matched on date and team: {r['compared']}")
    print(f"only in nba_api: {len(r['only_nba'])} {r['only_nba'][:6]}")
    print(f"only in ESPN:    {len(r['only_espn'])} {r['only_espn'][:6]}")
    if not r["mismatches"]:
        print(f"every one of the {len(FIGURES)} figures matches on all {r['compared']} matched team-games")
    for col, bad in r["mismatches"].items():
        print(f"MISMATCH {col}: {len(bad)} of {r['compared']}; first: {bad[:4]}")
    ok = not r["only_nba"] and not r["only_espn"] and not r["mismatches"]
    print("RESULT:", "identical" if ok else "DIFFERENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
