import hashlib
from pathlib import Path

ROOT = Path(r"C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship")
BASELINE = "F95BE5A2D31B617370918BE342E36CD03C4AF895806930DD209357937C60AB1C"
ADDED = '    monkeypatch.setattr(STRATEGY_ONLY_STAGES[0], "agent", orchestrator.PendingStrategyAgent(STAGE_SWOT))\n'

data = (ROOT / "tests" / "test_m3_orchestrator.py").read_bytes()
text = data.decode("utf-8")
newline = "\r\n" if "\r\n" in text else "\n"
line = ADDED.replace("\n", newline)
print("occurrences of added line:", text.count(line))
restored = text.replace(line, "", 1).encode("utf-8")
digest = hashlib.sha256(restored).hexdigest().upper()
print("hash with the line removed:", digest)
print("matches baseline:", digest == BASELINE)
for number, row in enumerate(text.splitlines(), 1):
    if row + newline == line:
        print("added at line", number)
