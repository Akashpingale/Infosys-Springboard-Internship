import json
import os
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.update({
    "LLM_API_KEY": "review" + "-llm-" + "placeholder",
    "LLM_MODEL": "review" + "-model",
    "TAVILY_API_KEY": "review" + "-tavily-" + "placeholder",
    "GROQ_API_KEY": "",
    "RUNS_DB_PATH": str(HERE / "review-spot-runs.db"),
})
real_connect = socket.socket.connect


def guarded(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError(f"review guard: network blocked ({host})")
    return real_connect(self, address)


socket.socket.connect = guarded

import pytest  # noqa: E402

from models.schemas import PipelineResult, StageError  # noqa: E402
from scripts import check_advisor_live, run_m3_live, run_m3_retro_live  # noqa: E402
from tests.m3_fakes import full_result  # noqa: E402

OUT = HERE / "review-spot-output"
BUSY = "The AI service is busy right now. Please try again in a minute."

failed = PipelineResult(
    status="failed",
    errors=[StageError(stage="extraction", code="llm_api_error", message=BUSY)],
    timings={"extraction": 1.25, "total": 1.25},
)
with pytest.MonkeyPatch.context() as patch:
    analysis, _ = full_result(patch)
skipped = analysis.model_copy(update={"status": "partial", "market": None, "competitors": None,
                                      "timings": {"extraction": 2.0, "search": 3.0, "total": 5.0}})
strategy_failed = analysis.model_copy(update={
    "status": "partial",
    "errors": [StageError(stage=key, code="llm_api_error", message=BUSY) for key in run_m3_live.STRATEGY_ONLY_KEYS],
})

for label, outcome in (("failed", failed), ("strategy_skipped", skipped), ("strategy_failed", strategy_failed)):
    out = OUT / label
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(run_m3_live, "strategy_pipeline", lambda submission, **kwargs: outcome)
        code = run_m3_live.main(["--fake", "--out", str(out)])
    summary = json.loads((out / run_m3_live.SUMMARY_NAME).read_text(encoding="utf-8"))
    first = summary["runs"][0]
    print(f"== L-1 with a {label} result -> exit {code}; executed {summary['ideas_executed']} of "
          f"{summary['ideas_attempted']}; status={first['status']} counts={first['counts']} "
          f"strategy_seconds={first['strategy_seconds']} violations={first['contract_violations']}")
    print("   files:", sorted(path.name for path in out.iterdir()))

saved_dir = OUT / "saved"
saved_dir.mkdir(parents=True, exist_ok=True)
saved = saved_dir / "agritech.json"
saved.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
with pytest.MonkeyPatch.context() as patch:
    patch.setattr(run_m3_retro_live, "strategy_pipeline", lambda submission, **kwargs: strategy_failed.model_copy(
        update={"timings": {**analysis.timings, "total": analysis.timings.get("total", 0.0) + 4.5,
                            "swot_risk": 1.5, "mvp_recommendation": 1.5, "go_to_market": 1.5}}))
    code = run_m3_retro_live.main(["--fake", "--saved", str(saved), "--out", str(OUT / "retro")])
retro = json.loads((OUT / "retro" / run_m3_retro_live.RETRO_SUMMARY_NAME).read_text(encoding="utf-8"))
print(f"== L-2 with every strategy stage failed -> exit {code}; status={retro['status']} seconds={retro['seconds']} "
      f"errors={len(retro['errors'])} counts={retro['counts']}")

saved_failed = saved_dir / "failed.json"
saved_failed.write_text(failed.model_dump_json(indent=2), encoding="utf-8")
code = check_advisor_live.main(["--fake", "--saved", str(saved_failed), "--out", str(OUT / "advisor_failed")])
print(f"== L-3 on a failed saved run -> exit {code}; out exists={(OUT / 'advisor_failed').exists()}")
saved_partial = saved_dir / "partial.json"
saved_partial.write_text(skipped.model_dump_json(indent=2), encoding="utf-8")
code = check_advisor_live.main(["--fake", "--saved", str(saved_partial), "--out", str(OUT / "advisor_partial")])
data = json.loads((OUT / "advisor_partial" / "advisor_partial.json").read_text(encoding="utf-8"))
print(f"== L-3 on a partial saved run without market and competitors -> exit {code}; statuses="
      f"{[entry.get('status') or entry['error'] for entry in data['questions']]} calls={data['calls']}")
print("== store file created:", (HERE / "review-spot-runs.db").exists())
