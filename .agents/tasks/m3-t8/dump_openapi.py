import json
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TARGET = HERE / "openapi-temp.json"
DB = HERE / f"lazy-{uuid.uuid4().hex}" / "runs.db"
os.environ.update({"TAVILY_API_KEY": "test-tavily-key", "LLM_API_KEY": "test-llm-key", "LLM_MODEL": "test-model",
                   "RUNS_DB_PATH": str(DB)})
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app import app  # noqa: E402

TARGET.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print("written", TARGET, "paths", len(app.openapi()["paths"]), "db_created", DB.exists(), "db_dir_created", DB.parent.exists())
