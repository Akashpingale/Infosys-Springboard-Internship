import re
import sys
from collections import Counter
from pathlib import Path

T19 = Path(__file__).resolve().parent.parent / "m3-t19"
pattern = re.compile(r"^\s*(?:\[\d+/\d+\]|ok \d+|✓\s+\d+|x\s+\d+)\s+\[(w\d+)\]\s+\S+\s+(e2e[\\/][^:]+):\d+:\d+")
for name in sys.argv[1:]:
    text = (T19 / name).read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "\n", text).replace("\r", "\n")
    specs = Counter()
    widths = Counter()
    seen = set()
    for line in text.splitlines():
        key = line.strip()
        if key in seen:
            continue
        seen.add(key)
        m = pattern.match(line)
        if m:
            specs[m.group(2).replace("\\", "/")] += 1
            widths[m.group(1)] += 1
    summary = [l.strip() for l in text.splitlines() if re.search(r"^\s*\d+ (passed|failed|flaky|skipped|did not run)", l)]
    print(name, dict(specs), dict(widths), summary)
