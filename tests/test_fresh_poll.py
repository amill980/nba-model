import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import daily_projections as dp
now = pd.Timestamp("2026-11-10T21:00:00Z")
def rows(cap, tip): return pd.DataFrame([dict(captured_utc=cap, commence_time_utc=tip)])
assert dp.needs_fresh_poll(pd.DataFrame(), now=now)                                             # no odds for today
assert dp.needs_fresh_poll(rows("2026-11-10T02:30:00Z", "2026-11-10T24:00:00Z".replace("24:00","23:59")), now=now)   # snapshot ~18 h old, game still to come
assert not dp.needs_fresh_poll(rows("2026-11-10T20:00:00Z", "2026-11-10T23:30:00Z"), now=now)   # 60 min old: fresh enough
assert not dp.needs_fresh_poll(rows("2026-11-10T02:30:00Z", "2026-11-10T20:30:00Z"), now=now)   # the only game already tipped
print("fresh-poll tests passed")
