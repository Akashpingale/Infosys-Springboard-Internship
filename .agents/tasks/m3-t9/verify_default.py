import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from frontend import analysis_views as current  # noqa: E402
from tests.conftest import FAKE_ENV  # noqa: E402
from tests.test_m3_report import STRATEGY_FIELDS, strategy_result  # noqa: E402


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def head_module():
    source = subprocess.run(["git", "show", "HEAD:frontend/analysis_views.py"], cwd=ROOT, capture_output=True, check=True).stdout
    path = Path(tempfile.mkdtemp()) / "analysis_views_head.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("analysis_views_head", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    head = head_module()
    with pytest.MonkeyPatch.context() as monkeypatch:
        for name, value in FAKE_ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = strategy_result(monkeypatch)
        no_strategy = strategy_result(monkeypatch, constraints=None)
    plain = result.model_copy(update=dict.fromkeys(STRATEGY_FIELDS))
    m2_only = result.model_copy(update={**dict.fromkeys(STRATEGY_FIELDS), "market": None, "competitors": None})
    checks = {
        "default_with_strategy": (head.report_markdown(result), current.report_markdown(result)),
        "default_without_strategy": (head.report_markdown(plain), current.report_markdown(plain)),
        "full_without_strategy": (head.report_markdown(plain, full=True), current.report_markdown(plain, full=True)),
        "default_m1_only": (head.report_markdown(m2_only), current.report_markdown(m2_only)),
        "full_m1_only": (head.report_markdown(m2_only, full=True), current.report_markdown(m2_only, full=True)),
        "default_assumed_constraints": (head.report_markdown(no_strategy), current.report_markdown(no_strategy)),
        "file_name": (head.report_file_name(result), current.report_file_name(result)),
    }
    report = {name: {"head": sha(a), "now": sha(b), "identical": a == b} for name, (a, b) in checks.items()}
    (OUT / "verify_default.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for name, entry in report.items():
        print(name, entry["identical"], entry["now"])
    if not all(entry["identical"] for entry in report.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
