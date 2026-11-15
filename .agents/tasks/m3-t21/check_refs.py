import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ["docs/11_milestone3_strategy_and_advisor.md", "docs/12_milestone3_test_report.md", "README.md", "docs/10_ui_design_system.md"]
TOKEN = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx))?:(\d+)`|`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|json|md|css))`")
TEST_NAME = re.compile(r"\btest_[a-z0-9_]+\b")
WEB_TITLE = re.compile(r"(?:MvpSection|GtmSection|AdvisorTab|StrategyTab) test \"([^\"]+)\"")
PREFIXES = ("agents/", "models/", "routes/", "utils/", "tests/", "scripts/", "frontend/", "web/", "docs/", "data/")
BASES = ("", "web/src/", "web/src/features/", "web/src/features/strategy/", "web/src/features/advisor/", "web/src/features/new-validation/", "web/")


def find(name: str) -> Path | None:
    for base in BASES:
        candidate = ROOT / base / name
        if candidate.exists():
            return candidate
    return None


def line_refs(name: str) -> tuple[int, list[str]]:
    problems: list[str] = []
    count = 0
    for number, line in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
        current: str | None = None
        for match in TOKEN.finditer(line):
            path, ref, plain = match.group(1), match.group(2), match.group(3)
            if plain:
                current = plain
                continue
            if path:
                current = path
            if current is None or ref is None:
                continue
            target = find(current)
            if target is None:
                problems.append(f"{name}:{number}: no file {current}")
                continue
            lines = target.read_text(encoding="utf-8").splitlines()
            index = int(ref)
            text = lines[index - 1].strip() if 0 < index <= len(lines) else "<beyond end of file>"
            count += 1
            print(f"{name}:{number}: {current}:{index}: {text[:110]}")
    return count, problems


def test_names(name: str, defined: set[str]) -> tuple[int, list[str]]:
    text = (ROOT / name).read_text(encoding="utf-8")
    names = sorted(set(TEST_NAME.findall(text)) - {"test_m3_", "test_runs", "test_ideas"})
    names = [entry for entry in names if not entry.startswith(("test_runs", "test_ideas", "test_m3_", "test_m2_", "test_run_store"))]
    missing = [f"{name}: test not defined: {entry}" for entry in names if entry not in defined]
    return len(names), missing


def web_titles(name: str, sources: str) -> tuple[int, list[str]]:
    text = (ROOT / name).read_text(encoding="utf-8")
    titles = WEB_TITLE.findall(text)
    missing = [f"{name}: web test title not found: {title}" for title in titles if f"'{title}'" not in sources and f'"{title}"' not in sources]
    return len(titles), missing


def files_named(name: str) -> tuple[int, list[str]]:
    text = (ROOT / name).read_text(encoding="utf-8")
    paths = sorted(set(re.findall(r"`((?:%s)[A-Za-z0-9_./*-]+)`" % "|".join(re.escape(prefix) for prefix in PREFIXES), text)))
    checked = 0
    missing: list[str] = []
    for path in paths:
        clean = path.split("::", 1)[0].rstrip("/")
        if "*" in clean or "{" in clean or clean.endswith((".json.", "/")):
            continue
        checked += 1
        if not (ROOT / clean).exists() and not (ROOT / clean.split(":", 1)[0]).exists():
            missing.append(f"{name}: path not found: {path}")
    return checked, missing


def main() -> int:
    defined = set()
    for path in (ROOT / "tests").glob("*.py"):
        defined |= set(re.findall(r"^def (test_[a-z0-9_]+)", path.read_text(encoding="utf-8"), re.MULTILINE))
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "web" / "src").rglob("*.test.ts*"))
    sources += "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "web" / "e2e").glob("*.ts"))
    problems: list[str] = []
    for name in DOCS:
        count, found = line_refs(name)
        problems += found
        names, missing = test_names(name, defined)
        problems += missing
        titles, absent = web_titles(name, sources)
        problems += absent
        paths, gone = files_named(name)
        problems += gone
        print(f"== {name}: {count} line refs, {names} test names, {titles} web test titles, {paths} paths")
    for problem in problems:
        print(f"PROBLEM {problem}")
    print(f"problems {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
