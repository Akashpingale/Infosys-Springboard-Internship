import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TARGET = ROOT / "web" / "src" / "test" / "strategyFixture.synthetic.json"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pytest  # noqa: E402

import config  # noqa: E402,F401

with pytest.MonkeyPatch.context() as monkeypatch:
    for name, value in {"TAVILY_API_KEY": "test-tavily-key", "LLM_API_KEY": "test-llm-key", "LLM_MODEL": "test-model"}.items():
        monkeypatch.setenv(name, value)
    for name in ("GROQ_API_KEY", "RUNS_DB_PATH"):
        monkeypatch.delenv(name, raising=False)

    from models.schemas import PipelineResult
    from orchestrator import STRATEGY_ONLY_STAGES, run_pipeline
    from scripts import check_m3_contracts
    from tests.m3_fakes import CONSTRAINTS, full_result
    from tests.pipeline_fakes import PIPELINE_SUBMISSION
    from tests.test_m3_gtm_agent import draft as gtm_draft
    from tests.test_m3_gtm_agent import use_mvp_reply, use_swot_reply
    from tests.test_m3_gtm_agent import use_reply as use_gtm_reply
    from tests.test_m3_mvp_agent import as_reply
    from tests.test_m3_mvp_agent import draft as mvp_draft
    from tests.test_m3_swot_agent import draft as swot_draft

    bare, _ = full_result(monkeypatch)
    use_swot_reply(monkeypatch, as_reply(swot_draft()))
    use_mvp_reply(monkeypatch, as_reply(mvp_draft()))
    use_gtm_reply(monkeypatch, as_reply(gtm_draft()))
    result = run_pipeline(PIPELINE_SUBMISSION, STRATEGY_ONLY_STAGES, prior=bare, constraints=CONSTRAINTS)
    TARGET.write_text(json.dumps(result.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    again = PipelineResult.model_validate_json(TARGET.read_text(encoding="utf-8"))
    print("status", again.status, "swot", again.swot is not None, "mvp", again.mvp is not None, "gtm", again.gtm is not None)
    print("constraints", again.constraints.model_dump(exclude_none=True) if again.constraints else None)
    print("bytes", TARGET.stat().st_size)
    code = check_m3_contracts.main([str(TARGET.relative_to(ROOT))])
    print("exit code", code)
