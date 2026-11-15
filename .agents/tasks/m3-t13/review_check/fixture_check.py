import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from models.schemas import PipelineResult

path = ROOT / "web" / "src" / "test" / "strategyFixture.synthetic.json"
raw = path.read_text(encoding="utf-8")
result = PipelineResult.model_validate(json.loads(raw))
print("valid", type(result).__name__, "swot", result.swot is not None, "mvp", result.mvp is not None, "gtm", result.gtm is not None)
print("constraints", result.constraints)
patterns = [r"AIza[0-9A-Za-z_\-]{10,}", r"gsk_[0-9A-Za-z]{10,}", r"tvly-[0-9A-Za-z]{10,}", r"sk-[0-9A-Za-z]{10,}", r"Bearer\s+[0-9A-Za-z._\-]{10,}", r"PRIVATE KEY"]
print("key-shaped", sum(len(re.findall(p, raw)) for p in patterns))
