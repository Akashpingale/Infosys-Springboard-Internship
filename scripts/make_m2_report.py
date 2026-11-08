"""Refresh the live-run section of docs/09_milestone2_test_report.md (Section 10.4).

    python scripts/make_m2_report.py

Reads only artefacts that already exist:

    docs/test_runs_m2/run_summary.json   written by scripts/run_live_m2.py

It never runs a test, never calls an API and never invents a result. Until a live run has been
made, every idea is reported as **Not executed** with the reason. The rest of the report, including
the automated-test table and the human review checklists, is left exactly as written.

Only the block between the two marker comments is replaced.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

REPORT_FILE = ROOT_DIR / "docs" / "09_milestone2_test_report.md"
SUMMARY_FILE = ROOT_DIR / "docs" / "test_runs_m2" / "run_summary.json"

START_MARKER = "<!-- live-runs:start -->"
END_MARKER = "<!-- live-runs:end -->"

TASK_4_IDEAS = ("agritech", "fintech_cashflow", "foodtech_surplus")
NOT_EXECUTED_REASON = "No live run has been made. Run `python scripts/run_live_m2.py --yes` with real keys."

COUNT_COLUMNS = (
    ("competitors", "Competitors"),
    ("segments", "Segments"),
    ("market_sources", "Market sources"),
    ("competitor_sources", "Competitor sources"),
)


def _shown(path: Path) -> str:
    """A readable path for the report: relative to the project when it sits inside it."""
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.name


def _violation_text(violations: dict) -> str:
    if not violations:
        return "-"
    parts = []
    for stage, problems in violations.items():
        if problems == ["not run"]:
            parts.append(f"{stage}: not run")
        elif problems:
            parts.append(f"{stage}: {len(problems)}")
        else:
            parts.append(f"{stage}: none")
    return "; ".join(parts)


def _executed_rows(runs: list[dict]) -> list[str]:
    header = "| Idea | Industry | Status | Total time | " + " | ".join(label for _, label in COUNT_COLUMNS) + " | Integrity violations |"
    divider = "|---|---|---|---:|" + "---:|" * len(COUNT_COLUMNS) + "---|"
    rows = [header, divider]
    for entry in runs:
        if not entry.get("executed"):
            rows.append(
                f"| `{entry.get('idea', '?')}` | - | **Not executed** | - | "
                + " | ".join("-" for _ in COUNT_COLUMNS)
                + f" | {entry.get('reason', 'unknown reason')} |"
            )
            continue
        counts = entry.get("counts", {})
        total = entry.get("timings", {}).get("total")
        cells = [str(counts.get(key)) if counts.get(key) is not None else "-" for key, _ in COUNT_COLUMNS]
        rows.append(
            f"| `{entry['idea']}` | {entry.get('industry', '-')} | {entry.get('status', '?')} | "
            f"{total:.1f}s | " + " | ".join(cells) + f" | {_violation_text(entry.get('integrity_violations', {}))} |"
        )
    return rows


def _not_executed_block() -> list[str]:
    lines = [
        f"No live run has been recorded. `{_shown(SUMMARY_FILE)}` does not exist yet.",
        "",
        "| Idea | Status | Reason |",
        "|---|---|---|",
    ]
    lines += [f"| `{name}` | **Not executed** | {NOT_EXECUTED_REASON} |" for name in TASK_4_IDEAS]
    return lines


def live_section() -> list[str]:
    """The live-run block, built only from artefacts that exist."""
    if not SUMMARY_FILE.exists():
        return _not_executed_block()
    try:
        summary = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [
            f"`{_shown(SUMMARY_FILE)}` exists but could not be read "
            f"({type(exc).__name__}), so no live result is shown here.",
            "",
            *_not_executed_block()[2:],
        ]

    runs = summary.get("runs") or []
    if not runs:
        return [
            f"`{_shown(SUMMARY_FILE)}` holds no run, so nothing was executed.",
            "",
            *_not_executed_block()[2:],
        ]

    executed = [entry for entry in runs if entry.get("executed")]
    lines = [
        f"From `{_shown(SUMMARY_FILE)}`, generated "
        f"{summary.get('generated', 'at an unrecorded time')} with model "
        f"`{summary.get('model', 'unrecorded')}`. "
        f"{len(executed)} of {summary.get('ideas_attempted', len(runs))} ideas executed.",
        "",
        *_executed_rows(runs),
    ]
    missing = [name for name in TASK_4_IDEAS if name not in {entry.get("idea") for entry in runs}]
    if missing:
        lines += ["", "Not attempted in that run: " + ", ".join(f"`{name}`" for name in missing) + "."]
    warned = [entry for entry in executed if entry.get("warnings")]
    if warned:
        lines += ["", "Warnings recorded:"]
        for entry in warned:
            lines.append(f"- `{entry['idea']}`:")
            lines += [f"  - {text}" for text in entry["warnings"]]
    return lines


def render(current: str) -> str:
    if START_MARKER not in current or END_MARKER not in current:
        raise SystemExit(
            f"{REPORT_FILE.name} is missing the {START_MARKER} / {END_MARKER} markers, so the live "
            "section cannot be replaced safely."
        )
    head, rest = current.split(START_MARKER, 1)
    _, tail = rest.split(END_MARKER, 1)
    block = "\n".join(live_section())
    stamp = f"_Live section refreshed {datetime.now():%Y-%m-%d %H:%M} by `scripts/make_m2_report.py`._"
    return f"{head}{START_MARKER}\n\n{stamp}\n\n{block}\n\n{END_MARKER}{tail}"


def main() -> int:
    if not REPORT_FILE.exists():
        print(f"{REPORT_FILE} does not exist. Nothing was written.")
        return 1
    current = REPORT_FILE.read_text(encoding="utf-8")
    REPORT_FILE.write_text(render(current), encoding="utf-8")
    state = "live results" if SUMMARY_FILE.exists() else "no live run yet"
    print(f"Refreshed the live-run section of {_shown(REPORT_FILE)} ({state}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
