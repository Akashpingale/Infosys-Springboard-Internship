import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CURRENT = ROOT / "web" / "src" / "features" / "run" / "RunPage.test.tsx"
ORIGINAL = HERE / "RunPage.test.tsx.orig"

EDITS = [
    (
        "shows the header, the status and the seven tabs",
        "shows the header, the status and the five tabs",
    ),
    (
        "['Overview', 'Market', 'Competitors', 'Strategy', 'Advisor', 'Sources', 'Run details']",
        "['Overview', 'Market', 'Competitors', 'Sources', 'Run details']",
    ),
    (
        "    await user.keyboard('{ArrowRight}');\n"
        "    expect(screen.getByRole('tab', { name: 'Strategy' })).toHaveAttribute('aria-selected', 'true');\n\n"
        "    await user.keyboard('{ArrowRight}');\n"
        "    expect(screen.getByRole('tab', { name: 'Advisor' })).toHaveAttribute('aria-selected', 'true');\n\n",
        "",
    ),
    (
        "expect(screen.getAllByRole('tab')).toHaveLength(7);",
        "expect(screen.getAllByRole('tab')).toHaveLength(5);",
    ),
]

text = CURRENT.read_text(encoding="utf-8")
for new, old in EDITS:
    assert text.count(new) == 1, new
    text = text.replace(new, old)
undone = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
original = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest().upper()
print("undone  ", undone)
print("original", original)
print("match", undone == original)
