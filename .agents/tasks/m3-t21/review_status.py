import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
groups: Counter = Counter()
other = []
for line in out.splitlines():
    code, name = line[:2], line[3:].strip().strip('"')
    kind = "untracked" if code == "??" else "modified" if "M" in code else f"other:{code}"
    if name.startswith(".agents/"):
        area = ".agents"
    elif "/" not in name:
        area = "root"
    elif name.startswith("web/src/"):
        area = "web/src"
    elif name.startswith("web/e2e/"):
        area = "web/e2e"
    elif name.startswith("web/"):
        area = "web/config"
    elif name.startswith("docs/assets/ui_v3/"):
        area = "docs/assets/ui_v3"
    elif name.startswith("docs/"):
        area = "docs"
    else:
        area = name.split("/", 1)[0]
    groups[(area, kind)] += 1
    if kind.startswith("other") or area == "root" or area == "docs" or area == "frontend":
        other.append(f"{code} {name}")
for key in sorted(groups):
    print(key, groups[key])
print("total", sum(groups.values()), "outside .agents", sum(v for (a, _), v in groups.items() if a != ".agents"))
print("\n".join(other))
