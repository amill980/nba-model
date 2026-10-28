import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ensure_report as er
t = lambda h: datetime(2026, 10, 28, h, 5)
assert er.should_run(t(12), False, False)          # noon, no report -> build
assert not er.should_run(t(11), False, False)      # before noon -> wait
assert not er.should_run(t(15), True, False)       # report exists -> nothing to do
assert not er.should_run(t(15), False, True)       # known no-games day -> stop trying
print("ensure_report tests passed")
