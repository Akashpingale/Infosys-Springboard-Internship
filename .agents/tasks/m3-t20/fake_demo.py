import os
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pytest  # noqa: E402

import config  # noqa: E402,F401

LOCAL = {"127.0.0.1", "::1", "localhost"}

with pytest.MonkeyPatch.context() as patch:
    for name, value in {"TAVILY_API_KEY": "test-tavily-key", "LLM_API_KEY": "test-llm-key", "LLM_MODEL": "test-model"}.items():
        patch.setenv(name, value)
    for name in ("GROQ_API_KEY", "RUNS_DB_PATH"):
        patch.delenv(name, raising=False)
    real_connect = socket.socket.connect

    def guarded(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOCAL:
            raise RuntimeError(f"network blocked ({host})")
        return real_connect(self, address)

    patch.setattr(socket.socket, "connect", guarded)

    from scripts import check_advisor_live, run_m3_live, run_m3_retro_live

    out = HERE / "fake-output"
    print("== run_m3_live exit", run_m3_live.main(["--fake", "--out", str(out)]))
    print("== run_m3_retro_live exit", run_m3_retro_live.main(["--fake", "--out", str(out)]))
    print("== check_advisor_live exit", check_advisor_live.main(["--fake", "--out", str(out), "--saved", str(out / "agritech.json")]))
