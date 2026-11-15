import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKIP = {".git", ".venv", "node_modules", ".agents", "__pycache__", ".pytest_cache", "dist", "test-results", "playwright-report", ".mypy_cache"}

cutoff = datetime.fromisoformat(sys.argv[1]).timestamp()
sub = sys.argv[2] if len(sys.argv) > 2 else ""
base = ROOT / sub
count = 0
newer = []
for path in base.rglob("*"):
    rel = path.relative_to(ROOT)
    if any(part in SKIP for part in rel.parts):
        continue
    if not path.is_file():
        continue
    count += 1
    mtime = path.stat().st_mtime
    if mtime > cutoff:
        newer.append((datetime.fromtimestamp(mtime).isoformat(timespec="seconds"), rel.as_posix()))
print(f"scanned {count} files under '{sub or '.'}', newer than {sys.argv[1]}: {len(newer)}")
for stamp, name in sorted(newer):
    print(stamp, name)
