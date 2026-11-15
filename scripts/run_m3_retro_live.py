import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import setup_logging  # noqa: E402
from models.schemas import PipelineResult  # noqa: E402
from orchestrator import STRATEGY_FIELDS, TOTAL_KEY  # noqa: E402
from scripts.run_m3_live import (  # noqa: E402
    IDEAS_DIR,
    LLM_KEYS,
    MSG_FAKE_RUN,
    MSG_LIVE_RUN,
    MSG_NO_FILES,
    STRATEGY_ITEMS,
    SUMMARY_NAME,
    Meter,
    checklist,
    clients,
    generated_at,
    metered,
    model_name,
    never,
    output_dir,
    parser,
    print_checklist,
    read_submission,
    ready,
    run_entry,
    run_line,
    run_markdown,
    say,
    seconds_text,
    shown,
    strategy_hints,
    write,
    write_json,
)
from utils.errors import StrategyAlreadyCompleteError, StrategyNotReadyError  # noqa: E402
from utils.run_manager import STRATEGY_ONLY_KEYS, strategy_pipeline, strategy_time_limit_s  # noqa: E402

SAVED_RUN = ROOT_DIR / "docs" / "test_runs_m2" / "agritech.json"
RETRO_PREFIX = "retro_"
RETRO_SUMMARY_NAME = "retro_summary.json"

MSG_UNREADABLE = "The saved run {path} could not be read ({reason}). Nothing was run."
MSG_NO_IDEA_FILE = "There is no readable idea file {path} for this saved run ({reason}). Nothing was run."
MSG_NOT_READY = f"{StrategyNotReadyError.default_message} Nothing was run."
MSG_NOTHING_MISSING = f"{StrategyAlreadyCompleteError.default_message} Nothing was run."
MSG_NO_SEARCH = "A strategy job on a saved run makes no search: {searches} search request(s) were counted."
MSG_JOB_SECONDS = "The seconds below are those of this strategy job; the saved run keeps its own in the result file."
MSG_FULL_RUN = "The strategy part of the L-1 run of this idea took {seconds}."
MSG_NO_FULL_RUN = "No L-1 run of this idea is recorded in this folder to compare with."
HINT_FULL_RUN = "the strategy part of the L-1 run of this idea took {seconds}"
HINT_NO_FULL_RUN = "no L-1 run of this idea is recorded in this folder"


def missing_parts(result: PipelineResult) -> tuple[str, ...]:
    return tuple(key for key in STRATEGY_ONLY_KEYS if getattr(result, STRATEGY_FIELDS[key]) is None)


def full_run_strategy_seconds(out: Path, name: str) -> float | None:
    try:
        runs = json.loads((out / SUMMARY_NAME).read_text(encoding="utf-8")).get("runs") or []
        return next((run.get("strategy_seconds") for run in runs if run.get("idea") == name and run.get("executed")), None)
    except (OSError, ValueError, AttributeError):
        return None


def main(argv: list[str] | None = None) -> int:
    found = parser("Add the strategy stages to a saved run, reusing its idea and analyses, with no search (plan L-2).")
    found.add_argument(
        "--saved", type=Path, default=SAVED_RUN,
        help="the saved PipelineResult JSON to add the strategy to (default: docs/test_runs_m2/agritech.json)",
    )
    args = found.parse_args(argv)
    if not ready(args, "run_m3_retro_live.py", LLM_KEYS):
        return 1
    try:
        prior = PipelineResult.model_validate_json(args.saved.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        say(MSG_UNREADABLE.format(path=shown(args.saved), reason=type(exc).__name__))
        say(MSG_NO_FILES)
        return 1
    name = args.saved.stem
    idea_file = IDEAS_DIR / f"{name}.json"
    try:
        submission = read_submission(idea_file)
    except (OSError, ValueError, TypeError) as exc:
        say(MSG_NO_IDEA_FILE.format(path=shown(idea_file), reason=type(exc).__name__))
        say(MSG_NO_FILES)
        return 1
    if prior.idea is None or (prior.market is None and prior.competitors is None):
        say(MSG_NOT_READY)
        say(MSG_NO_FILES)
        return 1
    rerun = missing_parts(prior)
    if not rerun:
        say(MSG_NOTHING_MISSING)
        say(MSG_NO_FILES)
        return 1

    setup_logging()
    out = output_dir(args)
    generated = generated_at()
    summary = {"generated": generated, "fake": args.fake, "model": model_name(args.fake), "saved": shown(args.saved),
               "idea": name, "stages_run": list(rerun)}
    say(MSG_FAKE_RUN if args.fake else MSG_LIVE_RUN)
    say(f"Adding {len(rerun)} strategy stage(s) to {shown(args.saved)}.\n")
    meter = Meter()
    try:
        with clients(args.fake, strategy=True), metered(meter):
            result = strategy_pipeline(
                submission, idea=None, on_event=meter.on_event, should_stop=never,
                time_limit_s=strategy_time_limit_s(), strategy_time_limit_s=None,
                constraints=prior.constraints, prior=prior, rerun=rerun,
            )
    except Exception as exc:
        say(f"{name:<18} FAILED: unexpected error ({type(exc).__name__})")
        write_json(out / RETRO_SUMMARY_NAME, {**summary, "executed": False, "reason": f"unexpected error ({type(exc).__name__})"})
        say(f"Summary: {out / RETRO_SUMMARY_NAME}")
        return 1

    entry = {**summary, "executed": True, **run_entry(result, meter, rerun),
             "full_run_strategy_seconds": full_run_strategy_seconds(out, name)}
    entry["seconds"][TOTAL_KEY] = round(result.timings[TOTAL_KEY] - prior.timings.get(TOTAL_KEY, 0.0), 3)
    compared = entry["full_run_strategy_seconds"]
    notes = [
        MSG_NO_SEARCH.format(searches=entry["calls"][TOTAL_KEY]["searches"]),
        MSG_NO_FULL_RUN if compared is None else MSG_FULL_RUN.format(seconds=seconds_text(compared)),
    ]
    hints = strategy_hints(entry)
    hints[8] += "; " + (HINT_NO_FULL_RUN if compared is None else HINT_FULL_RUN.format(seconds=seconds_text(compared)))
    review = checklist(STRATEGY_ITEMS, hints)
    write(out / f"{RETRO_PREFIX}{name}.json", result.model_dump_json(indent=2))
    write(out / f"{RETRO_PREFIX}{name}.md", run_markdown(
        f"Milestone 3 strategy on a saved run: {name}", entry, result, rerun, review,
        fake=args.fake, generated=generated, submission=submission,
        notes=[f"Saved run: {entry['saved']}", *notes, MSG_JOB_SECONDS],
    ))
    write_json(out / RETRO_SUMMARY_NAME, entry)
    say(run_line(name, entry))
    for note in notes:
        say(note)
    say()
    print_checklist(f"the strategy on {entry['saved']}", review)
    say(f"Saved to {out}")
    say(f"Summary: {out / RETRO_SUMMARY_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
