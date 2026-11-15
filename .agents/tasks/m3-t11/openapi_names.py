import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402

schema = create_app().openapi()
names = sorted(schema["components"]["schemas"])
print([name for name in names if "Chat" in name or "__" in name])
meta = schema["paths"]["/api/meta"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
print(meta)
print(json.dumps(schema["components"]["schemas"]["MetaResponse"]["properties"]["chat"]))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(schema, indent=2), encoding="utf-8")
