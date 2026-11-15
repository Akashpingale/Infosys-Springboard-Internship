import re
from collections import defaultdict
from pathlib import Path

LOGS = Path(__file__).resolve().parents[1] / "m3-t19"
PROGRESS = re.compile(r"\[(\d+)/(\d+)\] \[(w\d+)\] \S+ e2e\\([\w\-]+\.spec\.ts)")
OK = re.compile(r"\bok\s+(\d+) \[(w\d+)\] \S+ e2e\\([\w\-]+\.spec\.ts)")
for name in ["pw-screens-3.log", "pw-gate.log", "resume-pw-focus.log"]:
    text = (LOGS / name).read_text(encoding="utf-8", errors="replace")
    seen = defaultdict(set)
    for m in PROGRESS.finditer(text):
        seen[m.group(4)].add(int(m.group(1)))
    for m in OK.finditer(text):
        seen[m.group(3)].add(int(m.group(1)))
    total = sum(len(v) for v in seen.values())
    parts = ", ".join(f"{spec} {len(nums)}" for spec, nums in sorted(seen.items()))
    print(f"{name}: {total} distinct test indexes; {parts}")
