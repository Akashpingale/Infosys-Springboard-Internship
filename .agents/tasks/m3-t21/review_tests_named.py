import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ["README.md", "docs/10_ui_design_system.md", "docs/11_milestone3_strategy_and_advisor.md", "docs/12_milestone3_test_report.md"]

defined: dict[str, list[str]] = {}
for path in (ROOT / "tests").glob("*.py"):
    for name in re.findall(r"^def (test_\w+)", path.read_text(encoding="utf-8"), re.M):
        defined.setdefault(name, []).append(path.name)

web_titles = set()
for path in (ROOT / "web" / "src").rglob("*.test.ts*"):
    web_titles.update(re.findall(r"\bit\(\s*['\"`](.+?)['\"`]\s*,", path.read_text(encoding="utf-8")))
spec_titles = set()
for path in (ROOT / "web" / "e2e").glob("*.spec.ts"):
    spec_titles.update(re.findall(r"\btest\(\s*['\"`](.+?)['\"`]\s*,", path.read_text(encoding="utf-8")))

missing = 0
checked = 0
for doc in DOCS:
    text = (ROOT / doc).read_text(encoding="utf-8")
    for span in re.findall(r"`([^`]+)`", text):
        m = re.fullmatch(r"(?:(tests/[\w./]+\.py)::)?(test_\w+)", span)
        if not m:
            continue
        checked += 1
        where = defined.get(m.group(2))
        if not where or (m.group(1) and Path(m.group(1)).name not in where):
            missing += 1
            print(f"MISSING {doc}: {span}")
    for title in re.findall(r"(?:Section|Tab|Tile|Run|States) test \"([^\"]+)\"", text):
        checked += 1
        if title not in web_titles:
            missing += 1
            print(f"MISSING web title {doc}: {title}")
    for path in re.findall(r"`((?:tests|scripts|agents|utils|routes|models|web/src|web/e2e|docs)/[\w./-]+\.\w+)`", text):
        checked += 1
        if not (ROOT / path).exists():
            missing += 1
            print(f"MISSING path {doc}: {path}")
    for path in re.findall(r"`(src/[\w./-]+\.\w+|e2e/[\w./-]+\.\w+)`", text):
        checked += 1
        if not (ROOT / "web" / path).exists():
            missing += 1
            print(f"MISSING web path {doc}: {path}")
print(f"checked {checked}, missing {missing}")
