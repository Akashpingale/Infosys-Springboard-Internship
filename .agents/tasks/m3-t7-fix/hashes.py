import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = [
    ".env.example", "agents/base.py", "agents/notices.py", "config.py", "models/api.py", "models/schemas.py",
    "orchestrator.py", "tests/test_run_store.py", "utils/deadline.py", "utils/errors.py", "utils/groq_client.py",
    "utils/llm_client.py", "utils/run_manager.py", "utils/run_store.py", "agents/gtm_agent.py", "agents/mvp_agent.py",
    "agents/strategy_checks.py", "agents/strategy_context.py", "agents/swot_risk_agent.py", "models/chat.py",
    "models/strategy_drafts.py", "tests/m3_fakes.py", "tests/test_m3_checks.py", "tests/test_m3_digest.py",
    "tests/test_m3_gtm_agent.py", "tests/test_m3_mvp_agent.py", "tests/test_m3_orchestrator.py",
    "tests/test_m3_schemas.py", "tests/test_m3_store_migration.py", "tests/test_m3_strict_schema.py",
    "tests/test_m3_swot_agent.py", "utils/chat_store.py",
]
ALLOWED = {"agents/gtm_agent.py", "tests/test_m3_gtm_agent.py"}
OUT = Path(__file__).with_name("before.json")

current = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper() for name in FILES}
if sys.argv[1:] == ["save"]:
    OUT.write_text(json.dumps(current, indent=1), encoding="utf-8")
    for name, digest in current.items():
        print(digest, name)
else:
    before = json.loads(OUT.read_text(encoding="utf-8"))
    for name in FILES:
        state = "changed" if before[name] != current[name] else "unchanged"
        flag = "" if (state == "unchanged") != (name in ALLOWED) else "  <-- UNEXPECTED"
        print(f"{state:9} {current[name]} {name}{flag}")
