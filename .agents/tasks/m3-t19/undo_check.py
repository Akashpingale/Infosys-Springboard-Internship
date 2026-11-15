import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = ["web/e2e/mockApi.ts", "web/playwright.config.ts"]


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


for name in FILES:
    current = (ROOT / name).read_bytes().split(b"\n")
    diff = git("diff", "-U0", "--", name).decode("utf-8")
    removed = 0
    added: set[int] = set()
    for match in re.finditer(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        removed += int(match.group(1) if match.group(1) is not None else 1)
        start, count = int(match.group(2)), int(match.group(3) if match.group(3) is not None else 1)
        added.update(range(start - 1, start - 1 + count))
    undone = b"\n".join(line for index, line in enumerate(current) if index not in added)
    head = git("show", f"HEAD:{name}")
    print(name, "lines removed by edit:", removed, "lines added:", len(added),
          "undo sha256:", hashlib.sha256(undone).hexdigest(), "HEAD sha256:", hashlib.sha256(head).hexdigest(),
          "match", undone == head)
