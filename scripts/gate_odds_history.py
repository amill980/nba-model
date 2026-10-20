"""Gate O: validate the two Kaggle historical-odds files against our verified game logs.

Thresholds written BEFORE the first run (2026-10-19):
  O1 coverage   : for each of 2022-23..2025-26, >=98% of regular-season games matched on
                  (date, unordered team pair); among matched, final scores equal in >=99.5%.
  O2 plausibility (per season, matched games with a spread):
                  |mean(actual home margin + book home spread)| < 0.75 pt  and
                  SD of that residual between 10 and 14 pts; |mean(actual total - total)| < 1.5.
                  Spread favourite agrees with moneyline favourite in >=98% where moneylines exist.
  O3 cross-source (A = nba_2008-2026, B = MGM, shared games): spreads within 0.5 pt in >=90%,
                  totals within 1.0 pt in >=90%.
  O4 closing-ness proxy (shared games): the source whose spread has lower MAE vs actual
                  margin is closer to the close (closing lines are more accurate than openers);
                  reported, not pass/fail.
A failing gate means that source/season/field is NOT used. Output: data/gates/odds_gate.txt
"""
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
A_MAP = {"gs": "GSW", "no": "NOP", "ny": "NYK", "sa": "SAS", "utah": "UTA", "wsh": "WAS"}
B_MAP = {"Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "Charlotte": "CHA", "Chicago": "CHI",
         "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN", "Detroit": "DET", "Golden State": "GSW",
         "Houston": "HOU", "Indiana": "IND", "LA Clippers": "LAC", "LA Lakers": "LAL", "Memphis": "MEM",
         "Miami": "MIA", "Milwaukee": "MIL", "Minnesota": "MIN", "New Orleans": "NOP", "New York": "NYK",
         "Oklahoma City": "OKC", "Orlando": "ORL", "Philadelphia": "PHI", "Phoenix": "PHX",
         "Portland": "POR", "Sacramento": "SAC", "San Antonio": "SAS", "Toronto": "TOR", "Utah": "UTA",
         "Washington": "WAS"}
out = []
def log(s=""): print(s); out.append(s)

# our games: one row per game with unordered team key and home-away scores where determinable
frames = []
for s in SEASONS:
    d = pd.read_csv(ROOT / "data/games" / f"team_games_{s}_Regular_Season.csv"); d["season"] = s; frames.append(d)
g = pd.concat(frames)
rows = []
for gid, grp in g.groupby("GAME_ID"):
    t = dict(zip(grp.TEAM_ABBREVIATION, grp.PTS)); home = grp[~grp.MATCHUP.str.contains("@")]
    rows.append(dict(game_id=gid, season=grp.season.iloc[0], date=grp.GAME_DATE.iloc[0],
                     key=(grp.GAME_DATE.iloc[0], frozenset(t)), scores=t,
                     home=home.TEAM_ABBREVIATION.iloc[0] if len(home) == 1 else None))
ours = pd.DataFrame(rows)

def load_a():
    a = pd.read_csv(ROOT / "data/odds_history/nba_betting_data_2007_2026/nba_2008-2026.csv")
    a = a[a.regular == True].copy()
    for c in ("away", "home"): a[c] = a[c].map(lambda x: A_MAP.get(x, x.upper()))
    a["key"] = [(d, frozenset((h, w))) for d, h, w in zip(a.date, a.home, a.away)]
    a["home_spread"] = np.where(a.whos_favored == "home", -a.spread, a.spread)  # book notation
    return a

def load_b():
    b = pd.read_csv(ROOT / "data/odds_history/mgm_grand_nba/all_odds.csv")
    b["date"] = b.game_date.str[:10]
    b["home"] = b.home_team.map(B_MAP); b["away"] = b.away_team.map(B_MAP)
    b["key"] = [(d, frozenset((h, w))) for d, h, w in zip(b.date, b.home, b.away)]
    b["home_spread"] = b.spread_home_points; b["total"] = b.total_over_points
    return b

A, B = load_a(), load_b()
log(f"B unmapped teams: {int(B.home.isna().sum() + B.away.isna().sum())}")

def attach(src, name):
    m = ours.merge(src.drop_duplicates("key")[["key", "home", "away", "home_spread", "total"]
                   + (["score_home", "score_away"] if name == "A" else [])], on="key", how="left", suffixes=("", "_src"))
    return m

def evaluate(m, name):
    log(f"\n=== Source {name} ===")
    for s in SEASONS:
        x = m[m.season == s]; got = x[x.home_spread.notna()]
        cov = len(got) / len(x)
        res = []
        for _, r in got.iterrows():
            h = r.home_src; a_ = r.away
            sc = r.scores
            if h in sc and r.away in sc:
                res.append((sc[h] - sc[r.away], sc[h] + sc[r.away], r.home_spread, r.total))
        arr = np.array(res, dtype=float)
        resid = arr[:, 0] + arr[:, 2]; tres = arr[:, 1] - arr[:, 3]
        o2 = abs(np.nanmean(resid)) < 0.75 and 10 <= np.nanstd(resid) <= 14 and abs(np.nanmean(tres)) < 1.5
        line = (f"{s}: coverage={cov:.4f} ({len(got)}/{len(x)})  mean_resid={np.nanmean(resid):+.2f} "
                f"sd={np.nanstd(resid):.2f}  total_resid_mean={np.nanmean(tres):+.2f}  "
                f"O1_cov={'PASS' if cov >= .98 else 'FAIL'} O2={'PASS' if o2 else 'FAIL'}")
        log(line)
        if name == "A":
            bad = 0; n = 0
            for _, r in got.iterrows():
                if r.home_src in r.scores and r.away in r.scores:
                    n += 1
                    bad += not (r.scores[r.home_src] == r.score_home and r.scores[r.away] == r.score_away)
            log(f"      score agreement with game log: {1 - bad / max(n,1):.4f} (n={n}) {'PASS' if 1 - bad/max(n,1) >= .995 else 'FAIL'}")

evaluate(attach(A, "A"), "A")
evaluate(attach(B, "B"), "B")

# moneyline favourite agreement (A)
ml = A.dropna(subset=["moneyline_home", "moneyline_away"])
ml = ml[ml.date >= "2022-10-01"]
agree = ((ml.moneyline_home < ml.moneyline_away) == (ml.whos_favored == "home")).mean()
log(f"\nA moneyline rows 2022-23+: {len(ml)} (by season-end: {ml.groupby('season').size().to_dict()}); favourite agreement={agree:.4f}")
log("A moneyline availability by season: " + str(A[A.date >= '2022-10-01'].groupby('season').moneyline_home.apply(lambda s: round(s.notna().mean(), 3)).to_dict()))

# cross-source O3 / O4
shared = A.drop_duplicates("key").merge(B.drop_duplicates("key"), on="key", suffixes=("_a", "_b"))
shared = shared.merge(ours[["key", "scores"]], on="key")
log(f"\nShared games A&B: {len(shared)}")
ds = (shared.home_spread_a - shared.home_spread_b).abs(); dt = (shared.total_a - shared.total_b).abs()
log(f"O3 spreads within 0.5: {(ds <= .5).mean():.4f} {'PASS' if (ds <= .5).mean() >= .9 else 'FAIL'};  totals within 1.0: {(dt <= 1).mean():.4f} {'PASS' if (dt <= 1).mean() >= .9 else 'FAIL'}")
mae = {}
for nm in ("a", "b"):
    e = [abs((r.scores[r.home_a] - r.scores[r.away_a]) + r[f"home_spread_{nm}"]) for _, r in shared.iterrows()
         if r.home_a in r.scores and r.away_a in r.scores]
    mae[nm] = np.mean(e)
log(f"O4 spread MAE vs actual margin: A={mae['a']:.3f}  B={mae['b']:.3f} (lower = closer to the close)")
(ROOT / "data/gates/odds_gate.txt").write_text("\n".join(out))
