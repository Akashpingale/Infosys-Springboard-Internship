import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent


def read(path: Path) -> str:
    data = path.read_bytes()
    text = None
    for encoding in ("utf-8", "utf-16", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", "ignore")
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def backend() -> None:
    text = read(HERE / "pytest-collect-ids.log")
    files = Counter(line.split("::", 1)[0] for line in text.splitlines() if "::" in line)
    m3 = {name: count for name, count in files.items() if name.startswith("tests/test_m3_")}
    total = sum(files.values())
    collected = re.findall(r"(\d+) tests collected", text)
    print(f"backend: {len(files)} files, {total} tests; summary line: {collected}")
    print(f"backend M3 files: {len(m3)}, tests {sum(m3.values())}; other files {len(files) - len(m3)}, tests {total - sum(m3.values())}")
    for name, count in sorted(m3.items()):
        print(f"  {count:4d}  {name}")
    changed = ["tests/test_run_store.py"]
    for name in changed:
        print(f"  existing file edited in M3: {name} {files.get(name)}")


def frontend() -> None:
    text = read(TASKS / "m3-t19" / "npm-test.log")
    rows = re.findall(r"(src/\S+\.test\.tsx?) \((\d+) tests?\)", text)
    per_file = {name: int(count) for name, count in rows}
    totals = re.findall(r"Test Files\s+(\d+) passed \((\d+)\)|Tests\s+(\d+) passed \((\d+)\)", text)
    print(f"frontend: {len(per_file)} files, {sum(per_file.values())} tests; summary: {totals}")
    m3 = [
        "src/features/new-validation/ConstraintsPanel.test.tsx",
        "src/features/run/strategyRun.test.tsx",
        "src/features/advisor/useChat.test.tsx",
        "src/lib/strategy.test.ts",
        "src/features/strategy/StrategyTab.test.tsx",
        "src/features/strategy/RisksSection.test.tsx",
        "src/features/strategy/SwotSection.test.tsx",
        "src/lib/strategyClaims.test.ts",
        "src/features/strategy/MvpSection.test.tsx",
        "src/features/strategy/GtmSection.test.tsx",
        "src/features/results/OverviewStrategyTile.test.tsx",
        "src/features/advisor/AdvisorTab.test.tsx",
        "src/features/advisor/advisorRun.test.tsx",
        "src/lib/noRawHtml.test.ts",
        "src/features/run/exportRun.test.tsx",
    ]
    found = {name: per_file.get(name) for name in m3}
    print(f"frontend M3 files: {len(m3)}, tests {sum(value or 0 for value in found.values())}")
    for name in m3:
        print(f"  {found[name]!s:>4}  {name}")
    print(f"  RunPage.test.tsx (existing, edited) {per_file.get('src/features/run/RunPage.test.tsx')}")


def browser() -> None:
    for name in ("pw-gate.log", "pw-screens-3.log", "resume-pw-focus.log"):
        text = read(TASKS / "m3-t19" / name)
        specs = Counter(re.findall(r"e2e[\\/](\S+\.spec\.ts)", text))
        summary = re.findall(r"^\s*(\d+) passed \(([^)]+)\)", text, re.MULTILINE)
        failed = re.findall(r"^\s*(\d+) failed", text, re.MULTILINE)
        print(f"browser {name}: summary {summary}, failed {failed}, spec mentions {dict(specs)}")


if __name__ == "__main__":
    backend()
    frontend()
    browser()
