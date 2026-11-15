import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = Path(__file__).resolve().parent / "baseline"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if os.environ.get("M3T4_BASELINE") == "1":
    for name, path in (("orchestrator", BASELINE / "orchestrator.py"), ("utils.run_manager", BASELINE / "utils" / "run_manager.py")):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        if name == "utils.run_manager":
            import utils
            utils.run_manager = module

import orchestrator  # noqa: E402
from tests.conftest import block_network, fake_env  # noqa: E402,F401
from tests.pipeline_fakes import PIPELINE_SUBMISSION, use_full_pipeline  # noqa: E402
from tests.run_fakes import finished, store_in  # noqa: E402
from utils import run_manager  # noqa: E402


def digest(result):
    data = result.model_dump(mode="json", exclude={"timings"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest().upper()


def test_capture(monkeypatch, tmp_path):
    out = {"orchestrator_file": orchestrator.__file__, "run_manager_file": run_manager.__file__}
    use_full_pipeline(monkeypatch)
    events = []
    result = orchestrator.run_pipeline(
        PIPELINE_SUBMISSION, orchestrator.FULL_STAGES, on_event=lambda e: events.append([e.stage, e.kind, e.code, e.message])
    )
    out["stage_names"] = [stage.name for stage in orchestrator.FULL_STAGES]
    out["status"] = result.status
    out["timing_keys"] = sorted(result.timings)
    out["events"] = events
    out["result_sha256"] = digest(result)

    use_full_pipeline(monkeypatch)
    manager = run_manager.RunManager(store_in(tmp_path))
    try:
        detail = finished(manager, manager.start(PIPELINE_SUBMISSION).id)
    finally:
        manager.shutdown()
    out["manager_state"] = detail.state
    out["manager_message"] = detail.message
    out["manager_stages"] = [[s.key, s.label, s.status, s.message] for s in detail.stages]
    out["manager_status"] = detail.result.status
    out["manager_result_sha256"] = digest(detail.result)
    target = Path(os.environ["M3T4_OUT"])
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
