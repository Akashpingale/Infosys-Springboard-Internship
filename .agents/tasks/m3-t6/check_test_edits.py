import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASELINE = json.loads((ROOT / ".agents" / "tasks" / "m3-t6" / "baseline.json").read_text(encoding="utf-8"))["files"]
ADDED = '    monkeypatch.setattr(STRATEGY_ONLY_STAGES[1], "agent", orchestrator.PendingStrategyAgent(STAGE_MVP))\n'
ASSERT_NOW = '    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["MvpAgent", "PendingStrategyAgent"]\n'
ASSERT_BEFORE = '    assert [type(stage.agent).__name__ for stage in STRATEGY_ONLY_STAGES[1:]] == ["PendingStrategyAgent"] * 2\n'
EDITS = {
    "tests/test_m3_orchestrator.py": [(ADDED, "")],
    "tests/test_m3_swot_agent.py": [(ADDED, ""), (ASSERT_NOW, ASSERT_BEFORE)],
}

for name, edits in EDITS.items():
    text = (ROOT / name).read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    current = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    restored = text
    for now, before in edits:
        line = now.replace("\n", newline)
        print(name, "occurrences of edited line:", text.count(line))
        for number, row in enumerate(text.splitlines(), 1):
            if row + newline == line:
                print(name, "edited line at", number)
        restored = restored.replace(line, before.replace("\n", newline), 1)
    digest = hashlib.sha256(restored.encode("utf-8")).hexdigest().upper()
    print(name, "current:", current)
    print(name, "with the edits undone:", digest)
    print(name, "matches baseline:", digest == BASELINE[name])
