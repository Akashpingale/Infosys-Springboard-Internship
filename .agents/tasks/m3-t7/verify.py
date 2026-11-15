import hashlib
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASELINE = json.loads((ROOT / ".agents" / "tasks" / "m3-t7" / "baseline-hashes.json").read_text(encoding="utf-8"))
EXPECTED_CHANGES = {"orchestrator.py", "tests/test_m3_orchestrator.py", "tests/test_m3_swot_agent.py", "tests/test_m3_mvp_agent.py"}
SCANNED = ["agents/gtm_agent.py", "tests/test_m3_gtm_agent.py", *sorted(EXPECTED_CHANGES)]
PATTERNS = {
    "google": r"AIza[0-9A-Za-z_\-]{30,}",
    "groq": r"gsk_[0-9A-Za-z]{20,}",
    "tavily": r"tvly-[0-9A-Za-z_\-]{10,}",
    "secret key": r"sk-[0-9A-Za-z_\-]{20,}",
    "bearer": r"(?i)bearer\s+[0-9A-Za-z._~+/\-]{16,}",
    "private key": r"PRIVATE KEY",
}

unchanged, changed = [], []
for name, expected in BASELINE.items():
    if not isinstance(expected, str):
        continue
    digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper()
    (unchanged if digest == expected else changed).append((name, expected[:8], digest[:8]))
print(f"protected files: {len(unchanged)} unchanged, {len(changed)} changed")
for name, before, after in changed:
    print(f"  changed {name}: {before} -> {after} expected={name in EXPECTED_CHANGES}")
print("unexpected changes:", [name for name, _, _ in changed if name not in EXPECTED_CHANGES])

for name in ("agents/gtm_agent.py", "tests/test_m3_gtm_agent.py"):
    data = (ROOT / name).read_bytes()
    print(f"new {name}: {len(data.splitlines())} lines, sha256 {hashlib.sha256(data).hexdigest().upper()}")

hits = 0
for name in SCANNED:
    text = (ROOT / name).read_text(encoding="utf-8")
    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            hits += 1
            print(f"  secret-shaped hit in {name}: {label}")
print("secret scan hits:", hits)

source = (ROOT / "agents/gtm_agent.py").read_text(encoding="utf-8")
print("comment lines in gtm_agent.py:", sum(1 for line in source.splitlines() if line.strip().startswith("#")))
print("docstrings in gtm_agent.py:", source.count('"""'))
