"""Closing-line lock logic. Run: python tests/test_close_poll.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import archive_odds as ao
U = timezone.utc
now = datetime(2026, 10, 24, 22, 55, tzinfo=U)
tip = now + timedelta(minutes=5)          # tips in 5 minutes
# nothing polled recently -> poll
go, need = ao.needs_close_poll([tip], [now - timedelta(minutes=90)], now); assert go and need == [tip]
# a snapshot 8 minutes before tip already covers it -> no poll
go, _ = ao.needs_close_poll([tip], [tip - timedelta(minutes=8)], now); assert not go
# last snapshot 40 minutes before tip -> poll
go, _ = ao.needs_close_poll([tip], [tip - timedelta(minutes=40)], now); assert go
# tip is 25 minutes away -> too early
go, _ = ao.needs_close_poll([now + timedelta(minutes=25)], [], now); assert not go
# game already started -> never polled for a close
go, _ = ao.needs_close_poll([now - timedelta(minutes=5)], [], now); assert not go
# two tips in the same cluster need one poll (both listed, one call); a later tip is not yet due
tips = [tip, tip + timedelta(minutes=5), now + timedelta(minutes=60)]
go, need = ao.needs_close_poll(tips, [], now); assert go and len(need) == 2
# one poll covers tips up to 20 minutes after it: tip at +5 triggers a poll at `now`; a tip at +18 is then already covered
snap_now = [now]
go, _ = ao.needs_close_poll([now + timedelta(minutes=18)], snap_now, now + timedelta(minutes=10)); assert not go
# but a tip 25 minutes after that poll is not covered
go, _ = ao.needs_close_poll([now + timedelta(minutes=25)], snap_now, now + timedelta(minutes=12)); assert go
print("close-poll tests passed")
