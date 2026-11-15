import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NEW_FILES = (
    "scripts/run_m3_live.py",
    "scripts/run_m3_retro_live.py",
    "scripts/check_advisor_live.py",
    "docs/test_runs_m3/README.md",
    "tests/m3_live_fakes.py",
    "tests/test_m3_live_scripts.py",
)


def status_names() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    names = []
    for line in out.splitlines():
        name = line[3:].strip().strip('"')
        if " -> " in name:
            name = name.split(" -> ", 1)[1]
        if name.startswith(".agents/") or name.endswith(".env"):
            continue
        names.append(name)
    return sorted(names)


def digest(name: str) -> str:
    path = ROOT / name
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def main() -> None:
    baseline = json.loads((HERE / "baseline_hashes.json").read_text(encoding="utf-8"))
    current = {name: digest(name) for name in status_names()}
    print(f"baseline entries: {len(baseline)}; current uncommitted entries: {len(current)}")
    differing = []
    for name in sorted(set(baseline) | set(current)):
        if baseline.get(name) != current.get(name):
            kind = "new" if name not in baseline else ("gone" if name not in current else "changed")
            differing.append(f"{kind} {name}")
    print("differences vs baseline:")
    for line in differing:
        print("  " + line)
    tested = {}
    for line in (HERE / "tested-hashes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            parts = line.split()
            tested[parts[1].replace("\\", "/")] = parts[0].lower()
    print("new files vs tested-hashes.txt:")
    for name in NEW_FILES:
        path = ROOT / name
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        lines = len(path.read_text(encoding="utf-8").splitlines())
        same = "same" if tested.get(name) == digest(name) else "DIFFERENT"
        print(f"  {same} {digest(name)[:16]} lines={lines} mtime={mtime} {name}")


if __name__ == "__main__":
    main()
