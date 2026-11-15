import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
out = subprocess.run(
    [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
)
files = Counter()
functions = {}
for line in out.stdout.splitlines():
    if "::" not in line:
        continue
    path, rest = line.split("::", 1)
    files[path] += 1
    functions.setdefault(path, set()).add(rest.split("[", 1)[0])
tail = [l for l in out.stdout.splitlines() if re.search(r"\d+ tests? collected|error", l)]
print("exit", out.returncode, "| summary:", tail[-3:])
m3 = {k: v for k, v in files.items() if Path(k).name.startswith("test_m3_")}
old = {k: v for k, v in files.items() if k not in m3}
print(f"files {len(files)} total {sum(files.values())}")
print(f"m3 files {len(m3)} total {sum(m3.values())}")
print(f"other files {len(old)} total {sum(old.values())}")
for name in sorted(m3):
    print(f"  {Path(name).name} {m3[name]}")
for name in ("tests/test_m2_domains.py", "tests/test_m2_report.py", "tests/test_run_store.py"):
    print(name, files.get(name), "functions", len(functions.get(name, ())))
