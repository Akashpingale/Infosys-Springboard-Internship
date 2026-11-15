import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASELINE = json.loads((ROOT / ".agents" / "tasks" / "m3-t6" / "baseline.json").read_text(encoding="utf-8"))["files"]
text = (ROOT / "orchestrator.py").read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in text else "\n"
restored = text.replace("from agents.mvp_agent import MvpAgent" + nl, "", 1)
restored = restored.replace("(plan Task T7)", "(plan Tasks T6 and T7)", 1)
restored = restored.replace("StrategyStage(MvpAgent(), STRATEGY_TITLES[STAGE_MVP])", "StrategyStage(PendingStrategyAgent(STAGE_MVP), STRATEGY_TITLES[STAGE_MVP])", 1)
digest = hashlib.sha256(restored.encode("utf-8")).hexdigest().upper()
print("orchestrator restored matches baseline:", digest == BASELINE["orchestrator.py"])
