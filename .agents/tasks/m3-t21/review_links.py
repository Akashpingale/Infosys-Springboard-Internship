import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
DOCS = sys.argv[1:] or ["README.md", "docs/10_ui_design_system.md", "docs/11_milestone3_strategy_and_advisor.md", "docs/12_milestone3_test_report.md"]
LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def slugs(path: Path) -> set[str]:
    found: dict[str, int] = {}
    result = set()
    fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        text = re.sub(r"`([^`]*)`", r"\1", m.group(2))
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)
        slug = re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE).replace(" ", "-")
        count = found.get(slug, 0)
        found[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


total = broken = external = 0
for doc in DOCS:
    path = ROOT / doc
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for target in LINK.findall(text):
        if re.match(r"^[a-z]+:", target):
            external += 1
            continue
        total += 1
        file_part, _, anchor = target.partition("#")
        dest = path if not file_part else (path.parent / unquote(file_part)).resolve()
        if not dest.exists():
            broken += 1
            print(f"BROKEN {doc}: {target} (no such path)")
            continue
        if anchor and dest.suffix == ".md" and anchor not in slugs(dest):
            broken += 1
            print(f"BROKEN {doc}: {target} (no heading #{anchor})")
print(f"documents {len(DOCS)}, relative links {total}, external {external}, broken {broken}")
