import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

EDITS = {
    "web/src/features/run/RunPage.test.tsx": [
        ("import { META } from '@/test/fixtures';\nimport { renderWithApp } from '@/test/render';",
         "import { renderWithApp } from '@/test/render';"),
        ("  it('moves between tabs with the arrow keys', async () => {\n"
         "    server.use(show(DONE), http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)));",
         "  it('moves between tabs with the arrow keys', async () => {\n    server.use(show(DONE));"),
    ],
    "web/src/features/run/strategyRun.test.tsx": [
        ("  metaWithStrategy,\n  runUrl,\n  strategyOk,\n} from '@/test/strategyHandlers';",
         "  runUrl,\n  strategyOk,\n} from '@/test/strategyHandlers';"),
        ("  it('moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable', async () => {\n"
         "    server.use(show(DONE), metaWithStrategy());",
         "  it('moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable', async () => {\n"
         "    server.use(show(DONE));"),
        ("  it('opens the Strategy tab and a placeholder for the Advisor tab', async () => {\n"
         "    server.use(show(DONE), metaWithStrategy());",
         "  it('opens a placeholder for the Strategy and Advisor tabs', async () => {\n    server.use(show(DONE));"),
        ("expect(screen.getByRole('tabpanel')).toHaveTextContent('No strategy yet.');",
         "expect(screen.getByRole('tabpanel')).toHaveTextContent('The strategy for this validation will be shown here.');"),
    ],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


for name, pairs in EDITS.items():
    text = (ROOT / name).read_text(encoding="utf-8")
    for new, old in pairs:
        assert text.count(new) == 1, (name, new[:60])
        text = text.replace(new, old)
    reverted = sha(text.encode("utf-8"))
    original = sha((HERE / (Path(name).name + ".orig")).read_bytes())
    print(name, "current", sha((ROOT / name).read_bytes()))
    print(name, "reverted", reverted, "original", original, "match", reverted == original)
