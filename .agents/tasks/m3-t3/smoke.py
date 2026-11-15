import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from agents.strategy_context import build_digest
from models.schemas import PipelineResult

for name in ("liveAgritech", "liveFintech"):
    data = json.loads(Path(f"web/src/test/{name}.json").read_text(encoding="utf-8"))
    result = PipelineResult.model_validate(data["result"])
    digest = build_digest(result.idea, result.constraints, result.market, result.competitors)
    print(name, len(digest.text), len(digest.facts), digest.dropped, digest.fits)
    if "--show" in sys.argv:
        print(digest.text)
