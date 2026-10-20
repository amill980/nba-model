"""Synthetic checks of the Phase A logic. Run: python tests/test_phase_a.py"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import phase_a as pa

assert pa.norm_report("PippenJr.,Scotty") == pa.norm("Scotty Pippen Jr.") == "scottypippenjr"
assert pa.norm_report("Dončić,Luka") == pa.norm("Luka Dončić")

# players: HOM star Sam Star plays 30 min in 6 games; AWY player filler
rows = []
for i in range(6):
    d = f"2026-11-{10+i:02d}"
    rows.append(dict(PLAYER_NAME="Sam Star", TEAM_ABBREVIATION="HOM", GAME_DATE=d, GAME_ID=f"g{i}", MIN=30.0))
    rows.append(dict(PLAYER_NAME="Bench Guy", TEAM_ABBREVIATION="HOM", GAME_DATE=d, GAME_ID=f"g{i}", MIN=8.0))
players = pd.DataFrame(rows)
inj = pd.DataFrame([
    dict(report_time_et="12/01/26 11:30 AM", game_date="12/01/2026", matchup="AWY@HOM", team="HOM", player="Star,Sam", status="Out"),
    dict(report_time_et="12/01/26 11:30 AM", game_date="12/01/2026", matchup="AWY@HOM", team="HOM", player="Guy,Bench", status="Out"),   # <20 min: excluded
])
ev = pa.find_events(inj, players, "2026-12-15")
assert len(ev) == 1 and ev.iloc[0].player == "Star,Sam" and ev.iloc[0].news_side == "away", ev

# already out in previous game's final report -> not an event
inj2 = pd.concat([inj, pd.DataFrame([dict(report_time_et="11/15/26 05:00 PM", game_date="11/15/2026", matchup="AWY@HOM", team="HOM", player="Star,Sam", status="Out")])])
ev2 = pa.find_events(inj2, players, "2026-12-15")
assert (ev2.game_date != "2026-12-01").all() and (ev2.game_date == "2026-11-15").sum() == 1, ev2   # 11/15 is its own new event; 12/01 is not new

# odds: 3 snapshots; DK moves at the 13:00 poll, offshore books stale until 16:00; tip at 19:00 ET
def snap(t, h_by_book):
    return [dict(captured_utc=t, event_id="e1", commence_time_utc="2026-12-02T00:00:00Z", game_date_et="2026-12-01", home="HOM", away="AWY",
                 book=b, market="spreads", outcome="home", point=h) for b, h in h_by_book.items()]
books_old = dict(draftkings=-5, fanduel=-5, bovada=-5, betonlineag=-5)
odds = pd.DataFrame(snap("2026-12-01T15:00:00Z", books_old)                                   # 10:00 ET (before report)
                    + snap("2026-12-01T18:00:00Z", dict(draftkings=-3, fanduel=-3, bovada=-5, betonlineag=-5))   # 13:00 ET after report
                    + snap("2026-12-01T21:00:00Z", dict(draftkings=-3, fanduel=-3, bovada=-3, betonlineag=-3)))  # 16:00 ET
res = pa.evaluate_events(ev, odds, bettable=["bovada", "betonlineag"])
r = res.iloc[0]
assert r.status_note == "ok", r
# home player out -> home spread should rise; median pre -5, post (-3,-3,-5,-5)=-4 ; close -3
assert abs(r.consensus_pre - (-5)) < 1e-9 and abs(r.consensus_post - (-4)) < 1e-9
assert abs(r.response_pts - 1.0) < 1e-9, r.response_pts      # moved +1 in the news direction
# away bettor at stale -5 vs consensus close -3 -> +2 points beat the close
assert abs(r.stale_gap_pts - 2.0) < 1e-9, r.stale_gap_pts
assert r.book_lag_dev["bovada"] < r.book_lag_dev["draftkings"]
# cutoff guard
import subprocess
p = subprocess.run([sys.executable, str(Path(pa.__file__)), "--cutoff", "2026-12-16"], capture_output=True, text=True)
assert p.returncode != 0 and "Refused" in (p.stderr + p.stdout)
print("phase_a tests passed")
