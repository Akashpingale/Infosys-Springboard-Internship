import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASELINE = json.loads((ROOT / ".agents" / "tasks" / "m3-t7" / "baseline-hashes.json").read_text(encoding="utf-8"))
GTM_LINE = '    monkeypatch.setattr(STRATEGY_ONLY_STAGES[2], "agent", orchestrator.PendingStrategyAgent(STAGE_GTM))\n'
SWOT_NOW = '    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "GtmAgent"]\n'
SWOT_BEFORE = '    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]\n'
MVP_NOW = '    assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "GtmAgent"\n'
MVP_BEFORE = '    assert type(STRATEGY_ONLY_STAGES[2].agent).__name__ == "PendingStrategyAgent"\n'
IMPORT_NOW = "from agents.gtm_agent import GtmAgent\n"
DOC_NOW = '    """Stands in for a strategy agent that is not registered (tests use it). Its stage fails with\n'
DOC_BEFORE = '    """Stands in for a strategy agent until it is built (plan Task T7). Its stage fails with\n'
STAGE_NOW = "    StrategyStage(GtmAgent(), STRATEGY_TITLES[STAGE_GTM]),\n"
STAGE_BEFORE = "    StrategyStage(PendingStrategyAgent(STAGE_GTM), STRATEGY_TITLES[STAGE_GTM]),\n"
EDITS = {
    "orchestrator.py": [(IMPORT_NOW, ""), (DOC_NOW, DOC_BEFORE), (STAGE_NOW, STAGE_BEFORE)],
    "tests/test_m3_orchestrator.py": [(GTM_LINE, "")],
    "tests/test_m3_swot_agent.py": [(SWOT_NOW, SWOT_BEFORE), (GTM_LINE, "")],
    "tests/test_m3_mvp_agent.py": [(MVP_NOW, MVP_BEFORE), (GTM_LINE, "")],
}

for name, edits in EDITS.items():
    text = (ROOT / name).read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    current = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    restored = text
    for now, before in edits:
        line = now.replace("\n", newline)
        numbers = [number for number, row in enumerate(text.splitlines(), 1) if row + newline == line]
        print(f"{name}: edited line at {numbers} (occurrences {text.count(line)})")
        restored = restored.replace(line, before.replace("\n", newline), 1)
    digest = hashlib.sha256(restored.encode("utf-8")).hexdigest().upper()
    print(f"{name}: current {current}")
    print(f"{name}: with the edits undone {digest}")
    print(f"{name}: matches baseline {digest == BASELINE[name]}")
