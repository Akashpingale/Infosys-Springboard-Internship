import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

EDITS = {
    "web/src/features/strategy/StrategyTab.test.tsx": (
        "StrategyTab.test.tsx.orig",
        [
            (
                "toEqual(['SWOT', 'Risks', 'MVP plan']);",
                "toEqual(['SWOT', 'Risks']);",
            ),
        ],
    ),
    "web/src/lib/strategyClaims.test.ts": (
        "strategyClaims.test.ts.orig",
        [
            (
                "it('adds every SWOT point, every risk and every MVP feature, after the analyses', () => {",
                "it('adds every SWOT point and every risk, after the analyses', () => {",
            ),
            ("expect(added).toHaveLength(26);", "expect(added).toHaveLength(18);"),
            ("      ...Array(6).fill('Risks'),\n      ...Array(8).fill('MVP plan'),\n", "      ...Array(6).fill('Risks'),\n"),
            (
                "      'Farmers stay with the free app',\n      'Local language support',\n    ]);",
                "      'Farmers stay with the free app',\n    ]);",
            ),
        ],
    ),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


for name, (orig, hunks) in EDITS.items():
    current = (ROOT / name).read_bytes()
    text = current.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    for after, before in hunks:
        after = after.replace("\n", newline)
        before = before.replace("\n", newline)
        assert text.count(after) == 1, (name, after)
        text = text.replace(after, before)
    reverted = sha(text.encode("utf-8"))
    original = sha((HERE / orig).read_bytes())
    print(f"{name}\n  current  {sha(current)}\n  reverted {reverted}\n  orig     {original}\n  match    {reverted == original}")
