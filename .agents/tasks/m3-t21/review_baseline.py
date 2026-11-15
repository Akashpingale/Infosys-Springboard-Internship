import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
T20 = HERE.parent / "m3-t20"

t21 = json.loads((HERE / "baseline_hashes.json").read_text(encoding="utf-8"))
t20 = json.loads((T20 / "baseline_hashes.json").read_text(encoding="utf-8"))
tested = {}
for line in (T20 / "tested-hashes.txt").read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if len(parts) >= 2:
        tested[parts[1].replace("\\", "/")] = parts[0].lower()

print(f"t20 baseline {len(t20)}, t21 baseline {len(t21)}, t20 tested {len(tested)}")
for name in sorted(set(t20) | set(t21)):
    a, b = t20.get(name), t21.get(name)
    if a == b:
        continue
    if a is None:
        mark = "matches T20 tested" if tested.get(name) == b else "NOT in T20 tested"
        print(f"only in t21: {name} ({mark})")
    elif b is None:
        print(f"only in t20: {name}")
    else:
        print(f"differs: {name}")
missing = [n for n in tested if n not in t21]
print("tested files missing from t21 baseline:", missing)
for name in ("README.md", "docs/10_ui_design_system.md"):
    print(name, "in t20 baseline:", name in t20, "in t21 baseline:", name in t21)
