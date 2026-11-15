import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent

approved = json.loads((TASKS / "m3-t21" / "baseline_hashes.json").read_text(encoding="utf-8"))
approved = {name: value.lower() for name, value in approved.items()}
for line in (TASKS / "m3-t21" / "final-hashes-iter2.txt").read_text(encoding="utf-8-sig").splitlines():
    if line.strip():
        value, name = line.split(None, 1)
        approved[name.strip().lstrip(".\\").replace("\\", "/")] = value.lower()
current = json.loads((HERE / "baseline_hashes.json").read_text(encoding="utf-8"))
current = {name: value.lower() for name, value in current.items()}
differ = sorted(name for name in set(approved) | set(current) if approved.get(name) != current.get(name))
print(f"approved state (T21 baseline + T21 iteration-2 documents): {len(approved)} files")
print(f"start of final verification: {len(current)} files")
print(f"files that differ: {len(differ)}")
for name in differ:
    print(f"  {name}: approved={approved.get(name, 'absent')[:12]} now={current.get(name, 'absent')[:12]}")
