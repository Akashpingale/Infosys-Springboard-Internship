import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ITER1 = {
    "docs/10_ui_design_system.md": "4FEBE0DDCE3B38B882DD70AB98F7E08A5F1185BE926BD815CF982298D58160BC",
    "docs/12_milestone3_test_report.md": "410EABC88A4D5C2B94264603D1F7E5E54749C48D9E949A492F3403C5B22C6BC9",
}
EDITS = {
    "docs/12_milestone3_test_report.md": [
        (
            "to seven names and the arrow-key cycle gained Strategy and Advisor (plan Section 20.4). One of its\n"
            "tests, `moves between tabs with the arrow keys`, gained two MSW handlers (`/api/meta` and the chat\n"
            "thread), as setup only, for the requests the new tabs make.\n",
            "to seven names and the arrow-key cycle gained Strategy and Advisor (plan Section 20.4). Two of its\n"
            "tests gained MSW handlers, as setup only, for the requests the new tabs make.\n",
        ),
        (
            "| Browser tests | Playwright, specs named on the command line in three runs (section 2.3) |",
            "| Browser tests | Playwright, one spec at a time (section 2.3) |",
        ),
        (
            "`npm run test:e2e` runs all seven specs, including the screenshot spec. The results above therefore\n"
            "come from three runs that named their specs on the command line, never from the whole suite:\n"
            "`screens-m3.spec.ts` (42 tests); the four accessibility and keyboard specs, new and earlier,\n"
            "together (204 tests); and `focus-m3.spec.ts` (42 tests). The ui_v2 screenshot spec was in none of\n"
            "them. The new screens are listed in\n",
            "`npm run test:e2e` runs all seven specs, including the screenshot spec, which is why the specs were\n"
            "run one at a time. The new screens are listed in\n",
        ),
    ],
    "docs/10_ui_design_system.md": [
        (
            "The measured Milestone 3 results, in [docs/12](12_milestone3_test_report.md), come from three runs\n"
            "that named their specs on the command line, never from the whole suite: `screens-m3.spec.ts`; the\n"
            "four accessibility and keyboard specs together; and `focus-m3.spec.ts`. The ui_v2 screenshot spec\n"
            "was not run, so the images in `assets/ui_v2/` still show the interface before Milestone 3.\n",
            "During Milestone 3 the specs were run one at a time and the ui_v2 screenshot spec was not run, so\n"
            "the images in `assets/ui_v2/` still show the interface before Milestone 3. The measured results are\n"
            "in [docs/12](12_milestone3_test_report.md).\n",
        ),
    ],
}
for name, edits in EDITS.items():
    raw = (ROOT / name).read_bytes()
    text = raw.decode("utf-8")
    crlf = raw.count(b"\r\n")
    print(f"{name}: {len(text.splitlines())} lines now, CRLF {crlf}")
    for after, before in edits:
        found = text.count(after)
        print(f"  after-text occurrences {found}")
        text = text.replace(after, before, 1)
    undone = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    print(f"  undone lines {len(text.splitlines())}, sha256 {undone}, equals iteration 1: {undone == ITER1[name]}")
