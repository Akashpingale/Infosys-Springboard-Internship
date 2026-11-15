import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def files() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    names = []
    for line in out.splitlines():
        name = line[3:].strip().strip('"')
        if name.startswith(".agents/") or name.endswith(".env"):
            continue
        names.append(name)
    return sorted(names)


def digest(name: str) -> str:
    path = ROOT / name
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def main() -> None:
    mode = sys.argv[1]
    current = {name: digest(name) for name in files()}
    baseline = OUT / "baseline_hashes.json"
    if mode == "save":
        if baseline.exists():
            print("baseline exists, not overwritten")
            return
        baseline.write_text(json.dumps(current, indent=1), encoding="utf-8")
        print(f"saved {len(current)} files")
        return
    before = json.loads(baseline.read_text(encoding="utf-8"))
    for name in sorted(set(before) | set(current)):
        if before.get(name) != current.get(name):
            print(("new " if name not in before else "changed ") + name)


if __name__ == "__main__":
    main()
