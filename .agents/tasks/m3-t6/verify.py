import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASE = json.loads((ROOT / ".agents" / "tasks" / "m3-t6" / "baseline.json").read_text(encoding="utf-8"))
EXPECTED_CHANGES = {"orchestrator.py", "tests/test_m3_orchestrator.py", "tests/test_m3_swot_agent.py"}
SCANNED = ["agents/mvp_agent.py", "tests/test_m3_mvp_agent.py", "orchestrator.py", "tests/test_m3_orchestrator.py", "tests/test_m3_swot_agent.py"]
PATTERNS = [
    r"AIza[0-9A-Za-z_\-]{30,}",
    r"gsk_[0-9A-Za-z]{20,}",
    r"tvly-[0-9A-Za-z_\-]{10,}",
    r"sk-[0-9A-Za-z_\-]{20,}",
    r"(?i)bearer\s+[0-9A-Za-z._~+/\-]{16,}",
    r"PRIVATE KEY",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


db = ROOT / "data" / "runs.db"
stat = db.stat()
print("runs.db sha256 matches:", sha(db) == BASE["runs_db"]["sha256"])
print("runs.db size:", stat.st_size, stat.st_size == BASE["runs_db"]["size"])
mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print("runs.db lastWriteTimeUtc:", mtime, mtime == BASE["runs_db"]["lastWriteTimeUtc"])

unchanged, changed = 0, []
for name, digest in BASE["files"].items():
    now = sha(ROOT / name)
    if now == digest:
        unchanged += 1
    else:
        changed.append((name, digest, now))
print(f"files checked {len(BASE['files'])}, unchanged {unchanged}, changed {len(changed)}")
for name, before, now in changed:
    print("  changed:", name, before[:8], "->", now[:8], "expected" if name in EXPECTED_CHANGES else "UNEXPECTED")
for name in ("agents/mvp_agent.py", "tests/test_m3_mvp_agent.py"):
    path = ROOT / name
    print("new:", name, sha(path), len(path.read_text(encoding="utf-8").splitlines()), "lines")

hits = 0
for name in SCANNED:
    text = (ROOT / name).read_text(encoding="utf-8")
    for pattern in PATTERNS:
        for match in re.finditer(pattern, text):
            hits += 1
            print("  secret-shaped hit:", name, pattern)
print("secret scan hits:", hits)
