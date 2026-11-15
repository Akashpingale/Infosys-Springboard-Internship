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

schema = app.openapi()
TARGET.write_text(json.dumps(schema, indent=2), encoding="utf-8")
print("written", TARGET.name, "paths", len(schema["paths"]), "schemas", len(schema["components"]["schemas"]))
print("db_created", DB.exists(), "db_dir_created", DB.parent.exists())
for path, methods in schema["paths"].items():
    for method, operation in methods.items():
        codes = ", ".join(sorted(operation.get("responses", {})))
        print(f"| `{method.upper()}` | `{path}` | {codes} |")
