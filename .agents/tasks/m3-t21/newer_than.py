import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    since = datetime.fromisoformat(sys.argv[1])
    prefixes = tuple(sys.argv[2:])
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    names = sorted({name for name in listed.decode("utf-8").split("\0") if name})
    newer = []
    checked = 0
    for name in names:
        if name.startswith(".agents/"):
            continue
        if prefixes and not name.startswith(prefixes):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        checked += 1
        stamp = datetime.fromtimestamp(path.stat().st_mtime)
        if stamp > since:
            newer.append((stamp, name))
    print(f"checked {checked} files under {', '.join(prefixes) or 'the whole tree'} (not .agents/), newer than {since}: {len(newer)}")
    for stamp, name in sorted(newer):
        print(f"  {stamp:%Y-%m-%d %H:%M:%S}  {name}")


if __name__ == "__main__":
    main()
