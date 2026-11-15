import hashlib
from pathlib import Path

import pytest

from frontend import analysis_views as views
from tests.conftest import block_network, fake_env  # noqa: F401
from tests.test_m3_report import STRATEGY_FIELDS, strategy_result


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_print_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch)
    plain = result.model_copy(update=dict.fromkeys(STRATEGY_FIELDS))
    print()
    out = Path(__file__).resolve().parent
    (out / "snapshot_default.md").write_bytes(views.report_markdown(result).encode("utf-8"))
    (out / "snapshot_full.md").write_bytes(views.report_markdown(result, full=True).encode("utf-8"))
    print("default", sha(views.report_markdown(result)))
    print("full_plain", sha(views.report_markdown(plain, full=True)))
