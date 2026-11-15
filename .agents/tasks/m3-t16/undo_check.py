import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

EDITS = {
    "web/src/features/strategy/StrategyTab.test.tsx": (
        "StrategyTab.test.tsx.orig",
        [
            (
                "toEqual(['SWOT', 'Risks', 'MVP plan', 'Go-to-market']);",
                "toEqual(['SWOT', 'Risks', 'MVP plan']);",
            ),
        ],
    ),
    "web/src/lib/strategyClaims.test.ts": (
        "strategyClaims.test.ts.orig",
        [
            (
                "it('adds every SWOT point, every risk, every MVP feature and the go-to-market items, after the analyses', () => {",
                "it('adds every SWOT point, every risk and every MVP feature, after the analyses', () => {",
            ),
            ("expect(added).toHaveLength(37);", "expect(added).toHaveLength(26);"),
            (
                "      ...Array(8).fill('MVP plan'),\n"
                "      'Go-to-market: Positioning',\n"
                "      ...Array(6).fill('Go-to-market: Channels'),\n"
                "      ...Array(4).fill('Go-to-market: Early customers'),\n",
                "      ...Array(8).fill('MVP plan'),\n",
            ),
            (
                "      'Local language support',\n      SYNTHETIC_STRATEGY_RESULT.gtm!.positioning.statement,\n    ]);",
                "      'Local language support',\n    ]);",
            ),
            (
                "    expect(plantixMarket.map((claim) => claim.where)).toEqual([\n"
                "      'SWOT: Opportunities',\n"
                "      'SWOT: Threats',\n"
                "      'Go-to-market: Channels',\n"
                "    ]);",
                "    expect(plantixMarket.map((claim) => claim.where)).toEqual(['SWOT: Opportunities', 'SWOT: Threats']);",
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
