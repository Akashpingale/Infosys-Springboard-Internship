"""Capture the run API, /api/meta and OpenAPI responses for T8 before/after comparison.

Usage (from the repo root):
    $env:PYTHONIOENCODING="utf-8"
    .\.venv\Scripts\python.exe .agents\tasks\m3-t8\capture_api.py [label]

`label` defaults to "baseline" and names the outputs: <label>-api.json and <label>-openapi.json in
this folder. Fake keys only, network blocked, RUNS_DB_PATH and the run store in a temp folder; the
real data/runs.db is never opened. Volatile values are normalised: the run id becomes "<RUN_ID>"
wherever it appears (also inside strings), and every ISO-8601 timestamp string becomes "<TIMESTAMP>".
"""

import json
import os
import re
import socket
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LABEL = sys.argv[1] if len(sys.argv) > 1 else "baseline"

TMP = Path(tempfile.mkdtemp(prefix="m3t8-capture-"))
TMP_DB = TMP / "env-runs.db"

# Same environment as tests/conftest.py, set before config.py runs load_dotenv (which never overrides).
os.environ.update({"TAVILY_API_KEY": "test-tavily-key", "LLM_API_KEY": "test-llm-key", "LLM_MODEL": "test-model",
                   "RUNS_DB_PATH": str(TMP_DB)})
OPTIONAL_ENV = ("BACKEND_URL", "LLM_TIMEOUT_S", "SEARCH_TIMEOUT_S", "GROQ_API_KEY")

_real_connect = socket.socket.connect


def _guarded(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError(f"Network access is blocked (tried {host})")
    return _real_connect(self, address)


socket.socket.connect = _guarded
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from app import create_app  # noqa: E402
from tests.run_fakes import SUBMISSION, FakePipeline, manager_with, store_in  # noqa: E402

for name in OPTIONAL_ENV:  # as conftest does after .env has been loaded
    os.environ.pop(name, None)

TS = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


def normalise(value, run_id):
    if isinstance(value, dict):
        return {k: normalise(v, run_id) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v, run_id) for v in value]
    if isinstance(value, str):
        if TS.match(value):
            return "<TIMESTAMP>"
        return value.replace(run_id, "<RUN_ID>") if run_id else value
    return value


def main() -> None:
    real_db = ROOT / "data" / "runs.db"
    real_before = real_db.stat().st_mtime_ns if real_db.exists() else None

    app = create_app()
    import_created_env_db = TMP_DB.exists()
    store_dir = TMP / "store"
    store_dir.mkdir()
    pipeline = FakePipeline()
    app.state.run_manager = manager_with(store_in(store_dir), pipeline)
    out: dict = {"label": LABEL}
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            body = {"submission": SUBMISSION.model_dump(mode="json")}
            post = client.post("/api/runs", json=body)
            run_id = post.json().get("run_id")
            out["post_runs"] = {"status_code": post.status_code, "keys": sorted(post.json()),
                                "body": normalise(post.json(), run_id)}
            assert app.state.run_manager.wait(run_id, 10), "run did not finish"
            detail = client.get(f"/api/runs/{run_id}")
            d = detail.json()
            out["run_detail"] = {
                "status_code": detail.status_code,
                "top_level_keys": sorted(d),
                "state": d.get("state"),
                "result_status": (d.get("result") or {}).get("status"),
                "stage_keys": [s.get("key") for s in d.get("stages", [])],
                "stage_labels": [s.get("label") for s in d.get("stages", [])],
                "stage_statuses": [s.get("status") for s in d.get("stages", [])],
                "stage_entry_keys": [sorted(s) for s in d.get("stages", [])],
                "pipeline_calls_kwargs": [sorted(c) for c in pipeline.calls],
                "body": normalise(d, run_id),
            }
            listing = client.get("/api/runs")
            rows = listing.json().get("runs", [])
            out["run_list"] = {"status_code": listing.status_code, "top_level_keys": sorted(listing.json()),
                               "row_count": len(rows), "row_keys": sorted(rows[0]) if rows else [],
                               "body": normalise(listing.json(), run_id)}
            meta = client.get("/api/meta")
            out["meta"] = {"status_code": meta.status_code, "top_level_keys": sorted(meta.json()),
                           "body": meta.json()}
            openapi = client.get("/openapi.json")
            openapi_body = openapi.json()
    finally:
        app.state.run_manager.shutdown()

    real_after = real_db.stat().st_mtime_ns if real_db.exists() else None
    out["checks"] = {"importing_and_creating_app_created_RUNS_DB_PATH_file": import_created_env_db,
                     "real_runs_db_mtime_unchanged": real_before == real_after,
                     "openapi_status_code": openapi.status_code,
                     "openapi_paths": sorted(openapi_body.get("paths", {})),
                     "openapi_schemas": sorted(openapi_body.get("components", {}).get("schemas", {}))}

    (HERE / f"{LABEL}-api.json").write_text(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    (HERE / f"{LABEL}-openapi.json").write_text(
        json.dumps(openapi_body, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"post": out["post_runs"]["body"], "stage_keys": out["run_detail"]["stage_keys"],
                      "stage_labels": out["run_detail"]["stage_labels"],
                      "stage_statuses": out["run_detail"]["stage_statuses"],
                      "state": out["run_detail"]["state"], "result_status": out["run_detail"]["result_status"],
                      "detail_keys": out["run_detail"]["top_level_keys"], "row_keys": out["run_list"]["row_keys"],
                      "meta_keys": out["meta"]["top_level_keys"], "checks": out["checks"]}, indent=1))


if __name__ == "__main__":
    main()
