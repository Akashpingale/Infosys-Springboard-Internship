import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper() if path.is_file() else "MISSING"


def status_files() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    names = []
    for line in out.splitlines():
        name = line[3:].strip().strip('"')
        if name.startswith(".agents/") or name.endswith(".env"):
            continue
        names.append(name)
    return sorted(names)


def stamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    print("checked at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    baseline = json.loads((HERE / "baseline_hashes.json").read_text(encoding="utf-8"))
    current = {name: sha(ROOT / name).lower() for name in status_files()}
    print(f"\n[1] git-status files now {len(current)}, in T19 start baseline {len(baseline)}")
    diffs = []
    for name in sorted(set(baseline) | set(current)):
        if baseline.get(name) != current.get(name):
            kind = "new" if name not in baseline else ("gone" if name not in current else "changed")
            diffs.append((kind, name))
    print(f"    differing from baseline: {len(diffs)}")
    non_png = [d for d in diffs if not d[1].startswith("docs/assets/ui_v3/")]
    pngs = [d for d in diffs if d[1].startswith("docs/assets/ui_v3/")]
    for kind, name in non_png:
        print(f"    {kind} {name}")
    print(f"    plus {len(pngs)} docs/assets/ui_v3 entries, kinds: {sorted({k for k, _ in pngs})}")

    tested = {}
    for line in (HERE / "resume-final-hashes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(" ", 1)
            tested[name.strip()] = digest.strip().upper()
    mismatch = [name for name, digest in tested.items() if sha(ROOT / name) != digest]
    print(f"\n[2] resume-final-hashes.txt entries {len(tested)}, mismatching now {len(mismatch)}")
    for name in mismatch:
        print("    mismatch", name)
    e2e_now = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "web" / "e2e").iterdir() if p.is_file())
    v3_now = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "docs" / "assets" / "ui_v3").iterdir() if p.is_file())
    untracked_by_list = [n for n in e2e_now + v3_now + ["web/playwright.config.ts"] if n not in tested]
    print(f"    e2e files now {len(e2e_now)}, ui_v3 files now {len(v3_now)}, not in the tested list: {untracked_by_list}")

    tested_before = {}
    for line in (HERE / "resume-tested-hashes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(" ", 1)
            tested_before[name.strip()] = digest.strip().upper()
    changed_since_first = sorted(
        n for n in set(tested) | set(tested_before) if tested.get(n) != tested_before.get(n)
    )
    print(f"    resume-tested vs resume-final differ: {changed_since_first}")

    before = {}
    for line in (HERE / "ui_v2_hashes_before.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(" ", 1)
            before[name.strip()] = digest.strip().upper()
    v2_dir = ROOT / "docs" / "assets" / "ui_v2"
    now = {p.name: sha(p) for p in v2_dir.glob("*.png")}
    differ = sorted(n for n in set(before) | set(now) if before.get(n) != now.get(n))
    newest = max((p.stat().st_mtime for p in v2_dir.iterdir()), default=0)
    print(f"\n[3] ui_v2 PNGs before {len(before)}, now {len(now)}, differing {len(differ)} {differ}")
    print(f"    ui_v2 entries {len(list(v2_dir.iterdir()))}, newest write {datetime.fromtimestamp(newest)}")

    print("\n[4] newest writes per area")
    for area in ["web/src", "web/e2e", "docs/assets/ui_v3", "web/playwright.config.ts", "web/package.json",
                 "web/vite.config.ts", "agents", "models", "routes", "src", "utils", "tests", "frontend", "scripts",
                 "docs"]:
        path = ROOT / area
        if not path.exists():
            continue
        items = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        if not items:
            continue
        latest = max(items, key=lambda p: p.stat().st_mtime)
        print(f"    {area}: {stamp(latest)} {latest.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
