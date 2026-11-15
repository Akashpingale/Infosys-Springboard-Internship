import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LAUNCH = HERE / "review_guard_launch.py"
OUT = HERE / "review-fake-output"
DB = HERE / "review-runs.db"
PLACEHOLDERS = {
    "LLM_API_KEY": "review" + "-llm-" + "placeholder",
    "LLM_MODEL": "review" + "-model",
    "TAVILY_API_KEY": "review" + "-tavily-" + "placeholder",
    "GROQ_API_KEY": "",
}
PATTERNS = [r"AIza[0-9A-Za-z_\-]{20,}", r"gsk_[0-9A-Za-z]{20,}", r"tvly-[0-9A-Za-z\-]{10,}", r"sk-[0-9A-Za-z]{20,}",
            r"Bearer\s+[0-9A-Za-z\-_.]{10,}", r"PRIVATE KEY"]

env = dict(os.environ)
env.update(PLACEHOLDERS)
env.update({"PYTHONIOENCODING": "utf-8", "RUNS_DB_PATH": str(DB)})
shutil.rmtree(OUT, ignore_errors=True)
if DB.exists():
    DB.unlink()

plain = [
    ["scripts/run_m3_live.py", "--help"],
    ["scripts/run_m3_retro_live.py", "--help"],
    ["scripts/check_advisor_live.py", "--help"],
    ["scripts/run_m3_live.py"],
    ["scripts/run_m3_retro_live.py"],
    ["scripts/check_advisor_live.py"],
    ["scripts/run_m3_live.py", "--yes", "--fake"],
]
guarded = [
    ["scripts/run_m3_live.py", "--fake", "--out", str(OUT)],
    ["scripts/run_m3_retro_live.py", "--fake", "--out", str(OUT)],
    ["scripts/check_advisor_live.py", "--fake", "--out", str(OUT), "--saved", str(OUT / "agritech.json")],
]
printed_all = []


def show(command, done):
    shown = " ".join(Path(part).name if part.startswith(str(HERE)) else part for part in command)
    print(f"$ python {shown} -> exit {done.returncode}")
    print(done.stdout.rstrip())
    if done.stderr.strip():
        tail = done.stderr.strip().splitlines()
        print("STDERR (last lines):")
        print("\n".join(tail[-8:]))
    print()
    printed_all.append(done.stdout + done.stderr)


for command in plain:
    done = subprocess.run([str(PYTHON), "-B", *command], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8")
    show(command, done)
for command in guarded:
    done = subprocess.run([str(PYTHON), "-B", str(LAUNCH), *command], cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding="utf-8")
    show(command, done)

from models.schemas import PipelineResult  # noqa: E402

print("== output files:", sorted(path.name for path in OUT.iterdir()))
for name in ("agritech", "fintech_cashflow", "foodtech_surplus", "retro_agritech"):
    result = PipelineResult.model_validate_json((OUT / f"{name}.json").read_text(encoding="utf-8"))
    print(f"   {name}.json validates: status={result.status} swot={result.swot is not None} "
          f"mvp={result.mvp is not None} gtm={result.gtm is not None}")
summary = json.loads((OUT / "run_summary.json").read_text(encoding="utf-8"))
print("== run_summary:", {key: summary[key] for key in ("fake", "model", "ideas_attempted", "ideas_executed")})
for run in summary["runs"]:
    print(f"   {run['idea']}: status={run['status']} calls_total={run['calls']['total']} "
          f"violations={len(run['contract_violations'])} strategy_seconds={run['strategy_seconds']}")
retro = json.loads((OUT / "retro_summary.json").read_text(encoding="utf-8"))
print("== retro_summary:", {key: retro[key] for key in ("fake", "model", "saved", "stages_run", "executed", "status",
                                                         "full_run_strategy_seconds")}, "calls_total=", retro["calls"]["total"])
advisor = json.loads((OUT / "advisor_agritech.json").read_text(encoding="utf-8"))
print("== advisor:", {key: advisor[key] for key in ("fake", "model", "saved", "calls")})
for entry in advisor["questions"]:
    print(f"   {entry['number']} {entry['topic']}: status={entry.get('status')} error={entry['error']} "
          f"calls={entry['calls']} cited={entry.get('cited_sections')}")
for name in ("agritech.md", "retro_agritech.md", "advisor_agritech.md"):
    first = (OUT / name).read_text(encoding="utf-8").splitlines()[:3]
    print(f"== {name} starts: {first}")
contract = subprocess.run(
    [str(PYTHON), "-B", str(LAUNCH), "scripts/check_m3_contracts.py",
     *(str(OUT / f"{name}.json") for name in ("agritech", "fintech_cashflow", "foodtech_surplus", "retro_agritech"))],
    cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
)
print(f"== check_m3_contracts on the four results -> exit {contract.returncode}")
print(contract.stdout.rstrip())
texts = "\n".join(path.read_text(encoding="utf-8") for path in sorted(OUT.iterdir())) + "\n".join(printed_all)
leaks = [value for value in PLACEHOLDERS.values() if value and value in texts and value != PLACEHOLDERS["LLM_MODEL"]]
model_printed = PLACEHOLDERS["LLM_MODEL"] in "\n".join(printed_all)
model_in_files = PLACEHOLDERS["LLM_MODEL"] in "\n".join(path.read_text(encoding="utf-8") for path in OUT.iterdir())
hits = [pattern for pattern in PATTERNS if re.search(pattern, texts)]
print("== placeholder keys found in outputs or console:", leaks or "none")
print("== configured model name printed on the console:", model_printed, "| in fake files:", model_in_files)
print("== key-shaped patterns found:", hits or "none")
print("== store file created at RUNS_DB_PATH:", DB.exists())
print("== docs/test_runs_m3 contents:", sorted(path.name for path in (ROOT / "docs" / "test_runs_m3").iterdir()))
