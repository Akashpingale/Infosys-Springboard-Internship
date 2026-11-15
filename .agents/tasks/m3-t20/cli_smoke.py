import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = HERE / "cli-output"
DB = HERE / "cli-runs.db"

env = dict(os.environ)
env.update({
    "LLM_API_KEY": "test-llm-key",
    "LLM_MODEL": "test-model",
    "TAVILY_API_KEY": "test-tavily-key",
    "GROQ_API_KEY": "test-groq-placeholder",
    "PYTHONIOENCODING": "utf-8",
    "RUNS_DB_PATH": str(DB),
})
shutil.rmtree(OUT, ignore_errors=True)
commands = [
    ["scripts/run_m3_live.py", "--help"],
    ["scripts/run_m3_retro_live.py", "--help"],
    ["scripts/check_advisor_live.py", "--help"],
    ["scripts/run_m3_live.py"],
    ["scripts/run_m3_live.py", "--fake", "--out", str(OUT)],
    ["scripts/run_m3_retro_live.py", "--fake", "--out", str(OUT)],
    ["scripts/check_advisor_live.py", "--fake", "--out", str(OUT), "--saved", str(OUT / "agritech.json")],
]
for command in commands:
    done = subprocess.run([str(PYTHON), "-B", *command], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print("$ python", " ".join(Path(part).name if part.startswith(str(HERE)) else part for part in command), "-> exit", done.returncode)
    lines = done.stdout.strip().splitlines()
    print("\n".join(lines[:6] + (["..."] if len(lines) > 9 else []) + lines[-3:] if len(lines) > 9 else lines))
    if "Traceback" in done.stderr:
        print("STDERR:", done.stderr[-3000:])
    print()
print("files:", sorted(path.name for path in OUT.iterdir()))
print("store file created:", DB.exists())
