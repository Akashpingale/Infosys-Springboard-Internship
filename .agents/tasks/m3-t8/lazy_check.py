import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB = Path(tempfile.gettempdir()) / f"m3t8-final-lazy-{uuid.uuid4().hex}" / "runs.db"
os.environ["RUNS_DB_PATH"] = str(DB)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
print("before import exists:", DB.exists(), DB.parent.exists())

from app import app  # noqa: E402

print("imported app with", len(app.routes), "routes")
print("after import file exists:", DB.exists(), "folder exists:", DB.parent.exists())
