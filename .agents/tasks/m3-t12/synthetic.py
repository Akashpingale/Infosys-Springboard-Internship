import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pytest  # noqa: E402

import config  # noqa: E402,F401

with pytest.MonkeyPatch.context() as monkeypatch:
    for name, value in {"TAVILY_API_KEY": "test-tavily-key", "LLM_API_KEY": "test-llm-key", "LLM_MODEL": "test-model"}.items():
        monkeypatch.setenv(name, value)
    for name in ("GROQ_API_KEY", "RUNS_DB_PATH"):
        monkeypatch.delenv(name, raising=False)

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
    target = HERE / "synthetic_result.json"
    target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print("status", result.status, "warnings", len(result.warnings))
    print("tiers", [(f.id, f.tier, f.rank, f.essential, f.effort, f.score) for f in result.mvp.features])
    print("capacity", result.mvp.capacity_person_months, result.mvp.planned_person_months, result.mvp.over_capacity)
    print("channels", [(c.id, c.priority, c.start_here, c.cost_level, c.budget_conflict, c.uses_feature_ids, c.addresses_risk_ids) for c in result.gtm.channels])
    print("positioning", result.gtm.positioning.target_segment, "|", result.gtm.positioning.differentiator_status)
    print("risks", [(r.id, r.severity, r.category) for r in result.swot.risks])
    print("mitigates", [f.mitigates_risk_ids for f in result.mvp.features])
    print("---- contract script ----")
    code = check_m3_contracts.main([str(target.relative_to(ROOT))])
    print("exit code", code)
