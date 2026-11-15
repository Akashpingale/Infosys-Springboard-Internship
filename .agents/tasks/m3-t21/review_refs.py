import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "11_milestone3_strategy_and_advisor.md"
FULL = re.compile(r"^([\w./-]+\.(?:py|ts|tsx|css)):(\d+)$")
SHORT = re.compile(r"^:(\d+)$")

total = 0
for number, line in enumerate(DOC.read_text(encoding="utf-8").splitlines(), start=1):
    current = None
    refs = []
    for span in re.findall(r"`([^`]+)`", line):
        m = FULL.match(span)
        if m:
            current = m.group(1)
            refs.append((current, int(m.group(2))))
            continue
        m = SHORT.match(span)
        if m and current:
            refs.append((current, int(m.group(1))))
    if not refs:
        continue
    label = line.split("|")[1].strip() if line.startswith("|") else line[:40]
    print(f"--- doc line {number}: {label}")
    for path, target in refs:
        total += 1
        file = ROOT / path
        if not file.is_file():
            print(f"  MISSING FILE {path}:{target}")
            continue
        lines = file.read_text(encoding="utf-8").splitlines()
        text = lines[target - 1].strip() if 0 < target <= len(lines) else "<OUT OF RANGE>"
        print(f"  {path}:{target}: {text[:110]}")
print("total refs", total)
