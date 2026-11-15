import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LAUNCH = HERE / "review_guard_launch.py"
OUT = HERE / "review-nokeys-output"

env = dict(os.environ)
env.update({"LLM_API_KEY": "", "LLM_MODEL": "", "TAVILY_API_KEY": "", "GROQ_API_KEY": "",
            "PYTHONIOENCODING": "utf-8", "RUNS_DB_PATH": str(HERE / "review-nokeys-runs.db")})
shutil.rmtree(OUT, ignore_errors=True)
commands = [
    ["scripts/run_m3_live.py", "--yes", "--out", str(OUT / "yes")],
    ["scripts/run_m3_live.py", "--fake", "--out", str(OUT)],
    ["scripts/run_m3_retro_live.py", "--fake", "--out", str(OUT)],
    ["scripts/check_advisor_live.py", "--fake", "--out", str(OUT), "--saved", str(OUT / "agritech.json")],
]
for command in commands:
    done = subprocess.run([str(PYTHON), "-B", str(LAUNCH), *command], cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding="utf-8")
    lines = done.stdout.strip().splitlines()
    shown = " ".join(Path(part).name if part.startswith(str(HERE)) else part for part in command)
    print(f"$ python {shown} -> exit {done.returncode}")
    print("\n".join(line for line in lines if not line.startswith("  [ ]")))
    if "Traceback" in done.stderr:
        print("STDERR:", done.stderr[-2000:])
    print()
summary = json.loads((OUT / "run_summary.json").read_text(encoding="utf-8"))
print("statuses:", [run["status"] for run in summary["runs"]], "yes-folder exists:", (OUT / "yes").exists())
print("store file created:", (HERE / "review-nokeys-runs.db").exists())
