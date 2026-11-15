import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8-sig"))


base, post, final = load("baseline-hashes.json"), load("post-hashes.json"), load("final-hashes.json")
bf, pf, ff = base["files"], post["files"], final["files"]
print("baseline files", len(bf), "final files", len(ff))
print("changed vs baseline:", sorted(k for k in bf if ff.get(k) != bf[k]))
print("new vs baseline:", sorted(k for k in ff if k not in bf))
print("unchanged vs baseline:", len([k for k in bf if ff.get(k) == bf[k]]))
print("final == coder post capture:", ff == pf)
print("git:", final["git"], "db:", final["runs_db"])
for key in sorted(k for k in ff if k not in bf or ff[k] != bf[k]):
    print(f"  {key} {ff[key]}")

status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
before = (HERE / "baseline-git-status.txt").read_text(encoding="utf-8-sig").splitlines()
print("git status added:", sorted(set(status) - set(before)))
print("git status removed:", sorted(set(before) - set(status)))

tracked = ["app.py", "models/api.py", "routes/meta_routes.py", "routes/run_routes.py", "utils/run_manager.py"]
numstat = subprocess.run(["git", "diff", "--numstat", "--", *tracked], cwd=ROOT, capture_output=True, text=True).stdout
print("git diff --numstat vs HEAD (includes earlier M3 work for models/api.py, utils/run_manager.py):")
print(numstat.rstrip())
new = ["routes/strategy_routes.py", "tests/test_m3_runs_api.py", "tests/test_m3_strategy_route.py", "tests/test_m3_no_search.py"]
for path in new:
    print("new", path, "lines", len((ROOT / path).read_text(encoding="utf-8").splitlines()))

PATTERNS = {
    "google": r"AIza[0-9A-Za-z_\-]{20,}",
    "groq": r"gsk_[0-9A-Za-z]{10,}",
    "tavily": r"tvly-[0-9A-Za-z\-]{8,}",
    "openai": r"sk-[0-9A-Za-z_\-]{16,}",
    "bearer": r"Bearer\s+[0-9A-Za-z._\-]{16,}",
    "private_key": r"PRIVATE KEY",
}
scan = tracked + new + ["tests/test_m3_schemas.py"]
scan += [str(p.relative_to(ROOT)).replace("\\", "/") for p in HERE.iterdir() if p.is_file()]
hits = 0
for path in scan:
    text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    for name, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            if path.endswith("final_checks.py"):
                continue
            hits += 1
            print("HIT", path, name)
print("secret scan files", len(scan), "hits", hits)
