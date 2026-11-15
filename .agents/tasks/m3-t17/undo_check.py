import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

EDITS = {
    "web/src/features/run/strategyRun.test.tsx": (
        "strategyRun.test.tsx.orig",
        [
            (
                "import {\n  EMPTY_THREAD,\n  STRATEGY_DONE,\n  STRATEGY_RUNNING,\n  STRATEGY_STAGE_LABELS,\n  chatThreadOk,\n  metaWithStrategy,\n",
                "import {\n  STRATEGY_DONE,\n  STRATEGY_RUNNING,\n  STRATEGY_STAGE_LABELS,\n  metaWithStrategy,\n",
            ),
            (
                "  it('moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable', async () => {\n"
                "    server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));\n",
                "  it('moves through all seven with the arrow keys, wrapping at both ends, with one tab tabbable', async () => {\n"
                "    server.use(show(DONE), metaWithStrategy());\n",
            ),
            (
                "  it('opens the Strategy tab and the Advisor tab', async () => {\n"
                "    server.use(show(DONE), metaWithStrategy(), chatThreadOk(() => EMPTY_THREAD));\n",
                "  it('opens the Strategy tab and a placeholder for the Advisor tab', async () => {\n"
                "    server.use(show(DONE), metaWithStrategy());\n",
            ),
            (
                "    await waitFor(() =>\n"
                "      expect(screen.getByRole('tabpanel')).toHaveTextContent('Ask about your market, competitors, risks, MVP or launch plan.'),\n"
                "    );\n",
                "    expect(screen.getByRole('tabpanel')).toHaveTextContent('Questions about this validation will be answered here.');\n",
            ),
        ],
    ),
    "web/src/features/run/RunPage.test.tsx": (
        "RunPage.test.tsx.orig",
        [
            (
                "import { server } from '@/test/server';\nimport { EMPTY_THREAD, chatThreadOk } from '@/test/strategyHandlers';\n",
                "import { server } from '@/test/server';\n",
            ),
            (
                "    server.use(\n"
                "      show(DONE),\n"
                "      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)),\n"
                "      chatThreadOk(() => EMPTY_THREAD),\n"
                "    );\n",
                "    server.use(show(DONE), http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)));\n",
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
