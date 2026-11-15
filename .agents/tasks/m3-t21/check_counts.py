import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent
ROOT = HERE.parents[2]
DOCS = {
    "README": ROOT / "README.md",
    "docs10": ROOT / "docs" / "10_ui_design_system.md",
    "docs11": ROOT / "docs" / "11_milestone3_strategy_and_advisor.md",
    "docs12": ROOT / "docs" / "12_milestone3_test_report.md",
}
COUNT_PHRASE = re.compile(r"\b\d[\d,.]*\s*(?:tests?|passed|files|screens|screenshots|specs|kB|axe checks|hits)\b")


def read(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-16", "cp1252"):
        try:
            return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def one(pattern: str, text: str) -> str:
    found = re.findall(pattern, text, re.MULTILINE)
    if len(set(found)) != 1:
        raise SystemExit(f"measurement not unique for /{pattern}/: {found}")
    return found[0]


def measured() -> dict[str, object]:
    pytest_full = read(TASKS / "m3-t20" / "pytest-full-3.log")
    pytest_review = read(TASKS / "m3-t20" / "review-pytest-full.log")
    collect = read(HERE / "pytest-collect-ids.log")
    npm = read(TASKS / "m3-t19" / "npm-test.log")
    build = read(TASKS / "m3-t19" / "build.log")
    gate = read(TASKS / "m3-t19" / "pw-gate.log")
    screens = read(TASKS / "m3-t19" / "pw-screens-3.log")
    focus = read(TASKS / "m3-t19" / "resume-pw-focus.log")
    scan = read(HERE / "secret-scan.log")
    files = Counter(line.split("::", 1)[0] for line in collect.splitlines() if "::" in line)
    m3 = {name: count for name, count in files.items() if name.startswith("tests/test_m3_")}
    web = {name: int(count) for name, count in re.findall(r"(src/\S+\.test\.tsx?) \((\d+) tests?\)", npm)}
    web_new = {name: count for name, count in web.items() if name in NEW_WEB}
    gate_specs = Counter(re.findall(r"e2e[\\/](\S+\.spec\.ts)", gate))
    values = {
        "backend_passed": int(one(r"^(\d+) passed, 1 warning", pytest_full)),
        "backend_passed_review": int(one(r"^(\d+) passed, 1 warning", pytest_review)),
        "backend_collected": int(one(r"(\d+) tests collected", collect)),
        "backend_files": len(files),
        "m3_files": len(m3),
        "m3_tests": sum(m3.values()),
        "old_tests": sum(files.values()) - sum(m3.values()),
        "m3_per_file": m3,
        "web_files": int(one(r"Test Files\s+(\d+) passed", npm)),
        "web_tests": int(one(r"Tests\s+(\d+) passed", npm)),
        "web_new_files": len(web_new),
        "web_new_tests": sum(web_new.values()),
        "web_per_file": web_new,
        "entry": one(r"index-\S+\.js\s+([\d.]+) kB", build),
        "entry_gzip": one(r"index-\S+\.js\s+[\d.]+ kB\s+\S+\s+gzip:\s+([\d.]+) kB", build),
        "runpage": one(r"RunPage-\S+\.js\s+([\d.]+) kB", build),
        "runpage_gzip": one(r"RunPage-\S+\.js\s+[\d.]+ kB\s+\S+\s+gzip:\s+([\d.]+) kB", build),
        "gate_passed": int(one(r"^\s*(\d+) passed \(", gate)),
        "screens_passed": int(one(r"^\s*(\d+) passed \(", screens)),
        "focus_passed": int(one(r"^\s*(\d+) passed \(", focus)),
        "spec_a11y_m3": gate_specs["accessibility-m3.spec.ts"],
        "spec_kbd_m3": gate_specs["keyboard-m3.spec.ts"],
        "spec_a11y": gate_specs["accessibility.spec.ts"],
        "spec_kbd": gate_specs["keyboard.spec.ts"],
        "scan_listed": int(one(r"files listed (\d+)", scan)),
        "scan_scanned": int(one(r"scanned (\d+)", scan)),
        "scan_binary": int(one(r"binary skipped (\d+)", scan)),
        "scan_hits": int(one(r"total hits (\d+)", scan)),
    }
    values["new_pw"] = values["screens_passed"] + values["spec_a11y_m3"] + values["spec_kbd_m3"] + values["focus_passed"]
    values["old_pw_run"] = values["spec_a11y"] + values["spec_kbd"]
    values["pw_passed"] = values["new_pw"] + values["old_pw_run"]
    values["pw_total"] = values["pw_passed"] + SCREENSHOT_SPEC
    values["old_pw_total"] = values["old_pw_run"] + SCREENSHOT_SPEC
    return values


NEW_WEB = (
    "src/features/new-validation/ConstraintsPanel.test.tsx", "src/features/run/strategyRun.test.tsx",
    "src/features/advisor/useChat.test.tsx", "src/lib/strategy.test.ts", "src/features/strategy/StrategyTab.test.tsx",
    "src/features/strategy/RisksSection.test.tsx", "src/features/strategy/SwotSection.test.tsx",
    "src/lib/strategyClaims.test.ts", "src/features/strategy/MvpSection.test.tsx",
    "src/features/strategy/GtmSection.test.tsx", "src/features/results/OverviewStrategyTile.test.tsx",
    "src/features/advisor/AdvisorTab.test.tsx", "src/features/advisor/advisorRun.test.tsx",
    "src/lib/noRawHtml.test.ts", "src/features/run/exportRun.test.tsx",
)
SCREENSHOT_SPEC = 81


def expectations(v: dict[str, object]) -> list[tuple[str, str]]:
    rows = [
        ("README", f"python -m pytest                    # {v['backend_passed']} tests, no network"),
        ("README", f"The Milestone 3 tests are the {v['m3_files']} files `tests/test_m3_*.py`, {v['m3_tests']} tests in all"),
        ("README", f"The {v['old_tests']:,} backend tests from before Milestone 3 all still pass"),
        ("README", f"npm test               # {v['web_tests']} unit and component tests in {v['web_files']} files"),
        ("README", f"all {v['pw_total']} Playwright tests in Chromium"),
        ("README", f"81 for the earlier screens, {v['spec_a11y_m3']} for the Milestone 3 screens"),
        ("README", f"refresh the {v['screens_passed']} Milestone 3 screenshots"),
        ("README", f"and {v['new_pw']} for the 14 Milestone 3 screens"),
        ("README", f"Last runs, in Milestone 3: {v['web_tests']} unit tests passed; {v['pw_passed']} browser tests passed"),
        ("README", f"268.79 kB ({v['entry_gzip']} kB gzipped); and the backend suite at {v['backend_passed']} passed"),
        ("README", f"|-- tests/                     {v['backend_passed']} backend tests"),
        ("docs10", f"| `npm test` | {v['web_tests']} unit and component tests in {v['web_files']} files"),
        ("docs10", f"All {v['pw_total']} Playwright tests in Chromium"),
        ("docs10", f"sections 7 and 8 ({v['old_pw_total']}) and the Milestone 3 specs of section 11 ({v['new_pw']})"),
        ("docs10", f"81 for the screens above, {v['spec_a11y_m3']} for the Milestone 3 screens"),
        ("docs10", f"Refresh the {v['screens_passed']} Milestone 3 screenshots"),
        ("docs12", f"| Backend | `python -m pytest` | **{v['backend_passed']} passed**, 0 failed, 1 warning |"),
        ("docs12", f"**{v['web_tests']} passed** in {v['web_files']} files"),
        ("docs12", f"Entry chunk **{v['entry']} kB**, {v['entry_gzip']} kB gzipped"),
        ("docs12", f"**{v['pw_passed']} passed** in six specs. The ui_v2 screenshot spec ({SCREENSHOT_SPEC} tests) was not run"),
        ("docs12", f"`python -m pytest`: **{v['backend_passed']} passed**, 0 failed, 0 skipped, in {v['backend_files']} files"),
        ("docs12", f"That is the {v['old_tests']:,} tests from"),
        ("docs12", f"plus {v['m3_tests']} new tests in {v['m3_files']} files"),
        ("docs12", f"| **Milestone 3 total** | **{v['m3_tests']}** |"),
        ("docs12", f"**{v['web_tests']} passed** in {v['web_files']} files: the {v['web_tests'] - v['web_new_tests']} from before Milestone 3 in {v['web_files'] - v['web_new_files']} files, and {v['web_new_tests']} new in {v['web_new_files']} files"),
        ("docs12", f"| **Total** | **{v['web_new_tests']}** |"),
        ("docs12", f"Entry chunk {v['entry']} kB, {v['entry_gzip']} kB gzipped"),
        ("docs12", f"its chunk ({v['runpage']} kB, {v['runpage_gzip']} kB gzipped)"),
        ("docs12", f"| `e2e/screens-m3.spec.ts` (new) | {v['screens_passed']} | {v['screens_passed']} passed |"),
        ("docs12", f"| `e2e/accessibility-m3.spec.ts` (new) | {v['spec_a11y_m3']} | {v['spec_a11y_m3']} passed |"),
        ("docs12", f"| `e2e/keyboard-m3.spec.ts` (new) | {v['spec_kbd_m3']} | {v['spec_kbd_m3']} passed |"),
        ("docs12", f"| `e2e/focus-m3.spec.ts` (new) | {v['focus_passed']} | {v['focus_passed']} passed |"),
        ("docs12", f"| `e2e/accessibility.spec.ts` | {v['spec_a11y']} | {v['spec_a11y']} passed |"),
        ("docs12", f"| `e2e/keyboard.spec.ts` | {v['spec_kbd']} | {v['spec_kbd']} passed |"),
        ("docs12", f"| **Total** | **{v['pw_total']}** | **{v['pw_passed']} passed, {SCREENSHOT_SPEC} not run** |"),
        ("docs12", f"| {v['scan_listed']} | {v['scan_scanned']} | {v['scan_binary']} | **{v['scan_hits']}** |"),
        ("docs12", f"`screens-m3.spec.ts` ({v['screens_passed']} tests)"),
        ("docs12", f"together ({v['gate_passed']} tests)"),
        ("docs12", f"`focus-m3.spec.ts` ({v['focus_passed']} tests)"),
    ]
    rows += [("docs12", f"| `{name}` | {count} |") for name, count in v["m3_per_file"].items()]
    rows += [("docs12", f"| `{name}` | {count} |") for name, count in v["web_per_file"].items()]
    return rows


def main() -> int:
    v = measured()
    if v["backend_passed"] != v["backend_collected"] or v["backend_passed"] != v["backend_passed_review"]:
        raise SystemExit(f"backend counts disagree: {v['backend_passed']} {v['backend_collected']} {v['backend_passed_review']}")
    if v["gate_passed"] != v["spec_a11y_m3"] + v["spec_kbd_m3"] + v["spec_a11y"] + v["spec_kbd"]:
        raise SystemExit("gate spec counts do not add up")
    print({key: value for key, value in v.items() if not isinstance(value, dict)})
    texts = {key: path.read_text(encoding="utf-8") for key, path in DOCS.items()}
    missing = [(doc, phrase) for doc, phrase in expectations(v) if phrase not in texts[doc]]
    print(f"expected phrases {len(expectations(v))}, missing {len(missing)}")
    for doc, phrase in missing:
        print(f"MISSING in {doc}: {phrase}")
    for key, text in texts.items():
        for number, line in enumerate(text.splitlines(), 1):
            for phrase in COUNT_PHRASE.findall(line):
                print(f"count phrase {key}:{number}: {phrase}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
