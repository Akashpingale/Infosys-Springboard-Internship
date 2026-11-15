import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / ".agents" / "tasks" / "m3-t19" / "npm-test.log"
text = LOG.read_text(encoding="utf-8", errors="replace")
text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
rows = {}
for line in text.splitlines():
    m = re.search(r"(src/\S+\.test\.tsx?)\s+\((\d+) tests?", line)
    if m:
        rows[m.group(1)] = int(m.group(2))
tracked = set(subprocess.run(["git", "ls-files", "web/src"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split())
modified = set(subprocess.run(["git", "diff", "--name-only", "HEAD", "--", "web"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split())
new = {k: v for k, v in rows.items() if f"web/{k}" not in tracked}
old = {k: v for k, v in rows.items() if f"web/{k}" in tracked}
print(f"files {len(rows)} tests {sum(rows.values())}")
print(f"new files {len(new)} tests {sum(new.values())}")
for k in sorted(new):
    print(f"  {k} {new[k]}")
print(f"existing files {len(old)} tests {sum(old.values())}")
print("modified tracked files under web:")
for name in sorted(modified):
    print("  ", name)
on_disk = sorted(p.relative_to(ROOT / "web").as_posix() for p in (ROOT / "web" / "src").rglob("*.test.ts*"))
print("test files on disk:", len(on_disk), "missing from log:", [p for p in on_disk if p not in rows])
