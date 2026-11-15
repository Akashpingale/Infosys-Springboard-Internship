import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
target = Path(tempfile.gettempdir()) / "m3t4_lazy_check" / "runs.db"
if target.exists():
    target.unlink()
os.environ["RUNS_DB_PATH"] = str(target)

from app import app  # noqa: E402

print("after import, db exists:", target.exists())
schema = app.openapi()
print("openapi paths:", len(schema["paths"]))
print("db exists after openapi:", target.exists())

from fastapi.testclient import TestClient  # noqa: E402

with TestClient(app) as client:
    meta = client.get("/api/meta")
    print("meta status:", meta.status_code)
    print("meta stages:", [stage["key"] for stage in meta.json()["stages"]])
print("db exists after meta:", target.exists())
