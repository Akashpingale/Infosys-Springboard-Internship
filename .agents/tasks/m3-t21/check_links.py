import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ["README.md", "docs/10_ui_design_system.md", "docs/11_milestone3_strategy_and_advisor.md", "docs/12_milestone3_test_report.md"]
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`+[^`]*`+")
LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def prose_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((number, line))
    return lines


def slug(heading: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.replace("`", "").replace("*", "")
    text = text.strip().lower()
    text = "".join(char for char in text if char.isalnum() or char in " -_")
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, line in prose_lines(path.read_text(encoding="utf-8")):
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def markdown_files() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    names = sorted({name for name in listed.decode("utf-8").split("\0") if name})
    return [name for name in names if name.endswith(".md") and not name.startswith(".agents/") and "node_modules/" not in name]


def check(name: str) -> tuple[int, int, list[str]]:
    path = ROOT / name
    checked = external = 0
    broken: list[str] = []
    for number, line in prose_lines(path.read_text(encoding="utf-8")):
        for target in LINK.findall(INLINE_CODE.sub("", line)):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                external += 1
                continue
            checked += 1
            file_part, _, anchor = target.partition("#")
            resolved = path if not file_part else (path.parent / unquote(file_part)).resolve()
            if not resolved.exists():
                broken.append(f"{name}:{number}: missing target {target}")
                continue
            if anchor:
                if resolved.is_dir() or resolved.suffix.lower() != ".md":
                    broken.append(f"{name}:{number}: anchor on a non-Markdown target {target}")
                elif unquote(anchor).lower() not in anchors(resolved):
                    broken.append(f"{name}:{number}: no heading for anchor {target}")
    return checked, external, broken


def main() -> int:
    names = markdown_files() if "--all" in sys.argv else DEFAULT
    total_checked = total_external = 0
    all_broken: list[str] = []
    for name in names:
        checked, external, broken = check(name)
        total_checked += checked
        total_external += external
        all_broken += broken
        print(f"{name}: {checked} relative links checked, {external} external not fetched, {len(broken)} broken")
    for line in all_broken:
        print(f"  BROKEN {line}")
    print(f"files {len(names)}, relative links {total_checked}, external {total_external}, broken {len(all_broken)}")
    return 1 if all_broken else 0


if __name__ == "__main__":
    sys.exit(main())
