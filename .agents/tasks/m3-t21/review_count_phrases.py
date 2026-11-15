import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ["README.md", "docs/10_ui_design_system.md", "docs/11_milestone3_strategy_and_advisor.md", "docs/12_milestone3_test_report.md"]
PATTERN = re.compile(
    r"\b\d[\d,]*\s+(?:unit and component |backend |Playwright |browser |new |earlier |axe |keyboard |planted )?"
    r"(?:tests?|passed|files?|specs?|screens?|screenshots?|checks|cases|violations|hits|functions)\b"
    r"|\b\d+\s*(?:of|x|×)\s*\d+\b|\b\d{3}\.\d{2}\s*kB|\(\d+\)"
)
for doc in DOCS:
    for number, line in enumerate((ROOT / doc).read_text(encoding="utf-8").splitlines(), start=1):
        found = PATTERN.findall(line)
        if found:
            print(f"{doc}:{number}: {' | '.join(found)}")
