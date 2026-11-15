import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

baseline = json.loads((HERE / "baseline_hashes.json").read_text(encoding="utf-8"))
final = ROOT / ".agents" / "tasks" / "m3-t19" / "resume-final-hashes.txt"
checked = mismatched = 0
for line in final.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    value, name = line.split(maxsplit=1)
    name = name.strip().replace("\\", "/")
    path = ROOT / name
    now = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
    base = baseline.get(name)
    checked += 1
    if now != value.lower() or (base is not None and base != value.lower()):
        mismatched += 1
        print(f"MISMATCH {name}: t19={value[:12]} t20-baseline={(base or 'absent')[:12]} now={now[:12]}")
print(f"T19 final-state entries checked: {checked}; mismatches: {mismatched}")
