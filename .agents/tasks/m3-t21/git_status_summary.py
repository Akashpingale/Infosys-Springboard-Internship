import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AREAS = (
    ("agents/", "backend: agents"),
    ("models/", "backend: models"),
    ("routes/", "backend: routes"),
    ("utils/", "backend: utils"),
    ("tests/", "backend: tests"),
    ("scripts/", "scripts"),
    ("frontend/", "Streamlit (frontend/)"),
    ("web/e2e/", "web: browser tests"),
    ("web/src/", "web: app and unit tests"),
    ("web/", "web: config"),
    ("docs/assets/ui_v3/", "docs: ui_v3 screenshots"),
    ("docs/", "docs"),
    (".agents/", "workflow notes (.agents/)"),
)


def area(name: str) -> str:
    for prefix, label in AREAS:
        if name.startswith(prefix):
            return label
    return "repository root"


def main() -> None:
    out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    rows = [(line[:2], line[3:].strip().strip('"')) for line in out.splitlines() if line.strip()]
    counts = Counter((area(name), "modified" if code.strip() == "M" else "untracked" if code == "??" else code.strip()) for code, name in rows)
    print(f"git status --porcelain -uall: {len(rows)} entries")
    for (label, kind), count in sorted(counts.items()):
        print(f"  {label:32} {kind:10} {count}")
    print("modified, tracked (outside .agents/):")
    for code, name in rows:
        if code.strip() == "M" and not name.startswith(".agents/"):
            print(f"  {name}")


if __name__ == "__main__":
    main()
