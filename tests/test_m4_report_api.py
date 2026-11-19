import json
import re
import sqlite3
import threading
import time
from contextlib import closing
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from agents import report_agent
from agents.report_agent import report_fingerprint
from app import create_app
from frontend.analysis_views import report_markdown
from models.api import RunDetail
from models.report import MSG_NEWER_REPORT, MSG_UNREADABLE_REPORT, ParagraphBlock, ReportDocument, read_report
from models.schemas import IdeaSubmission, PipelineResult
from routes.meta_routes import APP_VERSION
from routes.report_routes import file_date, file_slug, report_file_name
from tests.m4_report_fixtures_synthetic import (
    full_document,
    synthetic_complete,
    synthetic_no_strategy,
    synthetic_partial,
)
from tests.run_fakes import FakePipeline, failing_result, manager_with
from tests.test_m4_report_agent import DRAFT, FakeWriter, use_writer
from tests.test_m4_render_pdf import bundled_fonts
from utils.errors import LLMAPIError
from utils.report_render_md import render_report_md
from utils.run_store import REDACTED, RunStore

RUNS = "/api/runs"
SUBMISSION = IdeaSubmission(
    idea_description="A phone app that detects crop diseases from a photo of a leaf for small farmers.",
    industry="Agriculture / AgriTech",
    target_customers="Small farmers in India",
    relevant_details="Starting with two farming cooperatives.",
)
BODY = {"submission": SUBMISSION.model_dump(mode="json")}
SECRET = "-".join(("planted", "configured", "value", "for", "report", "redaction"))
REPORT_KEYS = {"exists", "generated_at", "stale", "narrative_status"}
NO_REPORT = {"exists": False, "generated_at": None, "stale": False, "narrative_status": None}
SLUG_DATE = r"startup-validation_[a-z0-9-]{1,40}_[0-9]{4}-[0-9]{2}-[0-9]{2}"


def report_path(run_id: str, suffix: str = "") -> str:
    return f"{RUNS}/{run_id}/report{suffix}"


def error_of(response) -> dict:
    assert set(response.json()) == {"error"}, response.text
    return response.json()["error"]


class StrategyAdder:
    def __init__(self, final: PipelineResult) -> None:
        self.final = final
        self.calls = 0

    def __call__(self, submission, *, idea, on_event, should_stop, time_limit_s, strategy_time_limit_s,
                 constraints, prior, rerun) -> PipelineResult:
        self.calls += 1
        return self.final


class HeldWriter(FakeWriter):
    def __init__(self, *outcomes: Any) -> None:
        super().__init__(*(outcomes or (DRAFT,)))
        self.release = threading.Event()
        self.entered = threading.Event()

    def __call__(self, system: str, user: str) -> str:
        self.entered.set()
        assert self.release.wait(10), "the test never released the writer"
        return super().__call__(system, user)


@pytest.fixture
def no_fonts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "no-fonts"
    folder.mkdir()
    monkeypatch.setenv("REPORT_FONT_DIR", str(folder))
    return folder


@pytest.fixture
def fonts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = bundled_fonts(tmp_path / "fonts")
    monkeypatch.setenv("REPORT_FONT_DIR", str(folder))
    return folder


@pytest.fixture
def build(tmp_path: Path, no_fonts: Path):
    made = []

    def factory(final: PipelineResult | None = None, *, pipeline=None, strategy=None,
                secrets: tuple[str, ...] = ()) -> TestClient:
        store = RunStore(tmp_path / "runs.db", secrets=secrets)
        options = {"strategy": strategy} if strategy is not None else {}
        manager = manager_with(store, pipeline or FakePipeline(final or synthetic_complete()), **options)
        app = create_app()
        app.state.run_manager = manager
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()
        made.append((client, manager))
        return client

    yield factory
    for client, manager in made:
        client.__exit__(None, None, None)
        manager.shutdown()


@pytest.fixture
def client(build) -> TestClient:
    return build()


def finished_run(client: TestClient, body: dict | None = None) -> str:
    response = client.post(RUNS, json=body or BODY)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    assert client.app.state.run_manager.wait(run_id, 10), "the run did not finish in time"
    return run_id


def detail(client: TestClient, run_id: str) -> dict:
    response = client.get(f"{RUNS}/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def generate(client: TestClient, run_id: str, body: dict | None = None) -> dict:
    response = client.post(report_path(run_id), json=body) if body is not None else client.post(report_path(run_id))
    assert response.status_code == 200, response.text
    return response.json()


def in_thread(target, *args) -> tuple[threading.Thread, list]:
    out: list = []
    worker = threading.Thread(target=lambda: out.append(target(*args)))
    worker.start()
    return worker, out


def row_of(client: TestClient, run_id: str) -> dict | None:
    return client.app.state.run_manager._store.get(run_id)


def test_a_finished_run_says_it_has_no_report_yet(client: TestClient) -> None:
    run_id = finished_run(client)

    body = detail(client, run_id)

    assert set(body["report"]) == REPORT_KEYS
    assert body["report"] == NO_REPORT
    for suffix in ("", "/pdf", "/markdown"):
        response = client.get(report_path(run_id, suffix))
        assert response.status_code == 404
        assert error_of(response) == {"code": "report_not_found", "message": "Generate the report first."}


def test_generating_a_report_stores_it_and_the_run_detail_describes_it(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    writer = use_writer(monkeypatch)
    run_id = finished_run(client)

    body = generate(client, run_id)

    document = ReportDocument.model_validate(body)
    assert document.meta.run_id == run_id and document.meta.narrative_status == "ok"
    assert (document.meta.consistency.passed_count, document.meta.consistency.total_count) == (12, 12)
    assert len(writer.calls) == 1
    run = RunDetail.model_validate(detail(client, run_id))
    assert document.meta.source_fingerprint == report_fingerprint(run.result, run.constraints)
    assert detail(client, run_id)["report"] == {
        "exists": True, "generated_at": document.meta.generated_at, "stale": False, "narrative_status": "ok",
    }
    stored = row_of(client, run_id)
    assert stored["report_fingerprint"] == document.meta.source_fingerprint
    assert stored["report_generated_at"] == document.meta.generated_at
    assert read_report(json.loads(stored["report_json"])) == document
    assert client.get(report_path(run_id)).json() == body


def test_a_current_report_is_returned_as_stored_without_an_ai_request(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    writer = use_writer(monkeypatch)
    run_id = finished_run(client)
    first = generate(client, run_id)

    again = generate(client, run_id, {"force": False})
    rereads = [detail(client, run_id)["report"] for _ in range(2)]

    assert again == first
    assert len(writer.calls) == 1
    assert rereads[0] == rereads[1] and rereads[0]["stale"] is False


def test_force_builds_a_new_report_and_replaces_the_old(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    writer = use_writer(monkeypatch, DRAFT, LLMAPIError())
    run_id = finished_run(client)
    assert generate(client, run_id)["meta"]["narrative_status"] == "ok"

    replaced = generate(client, run_id, {"force": True})

    assert len(writer.calls) == 2
    assert replaced["meta"]["narrative_status"] == "failed"
    assert client.get(report_path(run_id)).json() == replaced
    assert detail(client, run_id)["report"]["narrative_status"] == "failed"


def test_without_the_narrative_no_ai_request_is_made(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    writer = use_writer(monkeypatch)
    run_id = finished_run(client)

    body = generate(client, run_id, {"narrative": False})

    assert writer.calls == []
    assert body["meta"]["narrative_status"] == "skipped" and body["meta"]["prompt_version"] is None
    assert detail(client, run_id)["report"]["narrative_status"] == "skipped"


def test_a_run_without_a_usable_result_has_no_report(monkeypatch: pytest.MonkeyPatch, build) -> None:
    writer = use_writer(monkeypatch)
    client = build(pipeline=FakePipeline(failing_result()))
    run_id = finished_run(client)

    response = client.post(report_path(run_id))

    assert response.status_code == 409
    assert error_of(response)["code"] == "report_unavailable"
    assert writer.calls == [] and row_of(client, run_id)["report_json"] is None


def test_a_run_that_is_still_going_has_no_report(monkeypatch: pytest.MonkeyPatch, build) -> None:
    writer = use_writer(monkeypatch)
    hold = threading.Event()
    pipeline = FakePipeline(synthetic_complete(), block=hold)
    client = build(pipeline=pipeline)
    response = client.post(RUNS, json=BODY)
    run_id = response.json()["run_id"]
    assert pipeline.reached.wait(10)
    try:
        refused = client.post(report_path(run_id))
    finally:
        hold.set()
        client.app.state.run_manager.wait(run_id, 10)

    assert refused.status_code == 409 and error_of(refused)["code"] == "report_unavailable"
    assert writer.calls == []


def test_an_unknown_run_answers_run_not_found_on_every_report_route(client: TestClient) -> None:
    calls = [
        client.post(report_path("absent")),
        client.get(report_path("absent")),
        client.get(report_path("absent", "/pdf")),
        client.get(report_path("absent", "/markdown")),
        client.delete(report_path("absent")),
    ]

    for response in calls:
        assert response.status_code == 404
        assert error_of(response)["code"] == "run_not_found"


def test_the_request_body_is_optional_and_strict(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)

    refused = client.post(report_path(run_id), json={"forse": True})
    wrong = client.post(report_path(run_id), json={"force": "always"})

    assert refused.status_code == 422 and error_of(refused)["code"] == "invalid_input"
    assert wrong.status_code == 422 and error_of(wrong)["code"] == "invalid_input"
    assert row_of(client, run_id)["report_json"] is None
    assert generate(client, run_id)["meta"]["narrative_status"] == "ok"


def test_adding_strategy_makes_the_report_out_of_date_and_regenerating_makes_it_current(
    monkeypatch: pytest.MonkeyPatch, build
) -> None:
    writer = use_writer(monkeypatch)
    adder = StrategyAdder(synthetic_complete())
    client = build(synthetic_no_strategy(), strategy=adder)
    run_id = finished_run(client)
    old = generate(client, run_id)

    started = client.post(f"{RUNS}/{run_id}/strategy", json={"mode": "missing"})
    assert started.status_code == 202, started.text
    assert client.app.state.run_manager.wait(run_id, 10)

    assert adder.calls == 1
    assert detail(client, run_id)["report"] == {
        "exists": True, "generated_at": old["meta"]["generated_at"], "stale": True, "narrative_status": "ok",
    }
    assert client.get(report_path(run_id)).json() == old
    assert client.get(report_path(run_id, "/markdown")).status_code == 200

    new = generate(client, run_id)

    assert len(writer.calls) == 2
    assert new["meta"]["source_fingerprint"] != old["meta"]["source_fingerprint"]
    assert detail(client, run_id)["report"]["stale"] is False
    assert "swot" in new["meta"]["sections_included"] and "swot" not in old["meta"]["sections_included"]


def test_a_second_request_while_one_is_writing_is_busy(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    writer = HeldWriter()
    monkeypatch.setattr(report_agent, "generate_json", writer)
    run_id = finished_run(client)

    worker, out = in_thread(client.post, report_path(run_id))
    assert writer.entered.wait(10)
    try:
        second = client.post(report_path(run_id), json={"force": True})
        removed = client.delete(report_path(run_id))
    finally:
        writer.release.set()
        worker.join(10)

    assert second.status_code == 409 and error_of(second)["code"] == "report_busy"
    assert removed.status_code == 409 and error_of(removed)["code"] == "report_busy"
    assert out[0].status_code == 200 and len(writer.calls) == 1
    assert generate(client, run_id)["meta"]["narrative_status"] == "ok"


def test_report_writing_shares_the_advisor_concurrency_limit(monkeypatch: pytest.MonkeyPatch, build) -> None:
    monkeypatch.setenv("CHAT_MAX_CONCURRENT", "1")
    writer = use_writer(monkeypatch)
    client = build()
    run_id = finished_run(client)
    gate = client.app.state.chat_gate

    with gate.slot():
        worker, out = in_thread(client.post, report_path(run_id))
        time.sleep(0.4)
        waiting = writer.calls == [] and worker.is_alive()
    worker.join(10)

    assert waiting, "the narrative waits for a free slot"
    assert out[0].status_code == 200 and len(writer.calls) == 1


def test_a_report_without_the_narrative_does_not_wait_for_a_slot(monkeypatch: pytest.MonkeyPatch, build) -> None:
    monkeypatch.setenv("CHAT_MAX_CONCURRENT", "1")
    writer = use_writer(monkeypatch)
    client = build()
    run_id = finished_run(client)

    with client.app.state.chat_gate.slot():
        body = generate(client, run_id, {"narrative": False})

    assert body["meta"]["narrative_status"] == "skipped" and writer.calls == []


def test_the_pdf_download_renders_the_stored_report(monkeypatch: pytest.MonkeyPatch, client: TestClient, fonts: Path) -> None:
    writer = use_writer(monkeypatch)
    run_id = finished_run(client)
    document = ReportDocument.model_validate(generate(client, run_id))

    response = client.get(report_path(run_id, "/pdf"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert disposition == f'attachment; filename="{report_file_name(document, "pdf")}"'
    assert disposition.startswith('attachment; filename="startup-validation_')
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) > 3 and "Contents" in reader.pages[0].extract_text()
    assert len(writer.calls) == 1


def test_the_markdown_download_renders_the_stored_report(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    writer = use_writer(monkeypatch)
    run_id = finished_run(client)
    document = ReportDocument.model_validate(generate(client, run_id))

    response = client.get(report_path(run_id, "/markdown"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"] == f'attachment; filename="{report_file_name(document, "md")}"'
    assert response.text == render_report_md(document)
    assert len(writer.calls) == 1


def test_missing_fonts_fail_the_pdf_only(monkeypatch: pytest.MonkeyPatch, client: TestClient, no_fonts: Path) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    generate(client, run_id)

    pdf = client.get(report_path(run_id, "/pdf"))

    assert pdf.status_code == 500
    error = error_of(pdf)
    assert error["code"] == "report_render_failed"
    assert error["message"].startswith("The report fonts are not installed. See the setup guide.")
    assert "IBMPlexSans-Regular.ttf" in error["message"] and str(no_fonts) not in error["message"]
    assert client.get(report_path(run_id, "/markdown")).status_code == 200
    assert client.get(report_path(run_id)).status_code == 200


def test_a_report_over_the_page_cap_is_refused_with_a_plain_error(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, fonts: Path
) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    document = ReportDocument.model_validate(generate(client, run_id))
    document.sections[1].blocks = [ParagraphBlock(text=f"Paragraph {index} " * 20) for index in range(1500)]
    client.app.state.run_manager.save_report(run_id, document)

    response = client.get(report_path(run_id, "/pdf"))

    assert response.status_code == 422
    assert error_of(response) == {
        "code": "report_too_large",
        "message": "The report is longer than 60 pages, so the PDF was not made. Markdown and JSON are available.",
    }
    assert client.get(report_path(run_id, "/markdown")).status_code == 200


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("CropScan: AI crop disease detection", "cropscan-ai-crop-disease-detection"),
        ("Caf\u00e9 Se\u00f1or \u00fcber", "cafe-senor-uber"),
        ('a"; filename=evil.exe\r\nX-Header: 1', "a-filename-evil-exe-x-header-1"),
        ("../../etc/passwd", "etc-passwd"),
        ("", "idea"),
        ("   ", "idea"),
        ("\u0915\u0943\u0937\u093f \U0001f600", "idea"),
        ("word " * 30, "word-word-word-word-word-word-word-word"),
    ],
)
def test_file_names_are_built_from_a_safe_slug_only(title: str, slug: str) -> None:
    assert file_slug(title) == slug
    assert len(slug) <= 40 and not slug.endswith("-")


def test_file_names_carry_the_report_date() -> None:
    assert file_date("2026-11-16T10:00:00+00:00") == "2026-11-16"
    for unusable in ("not a date", "\u0662\u0660\u0662\u0666-11-16"):
        assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", file_date(unusable))


def test_every_download_name_follows_the_pattern() -> None:
    document = full_document(synthetic_complete())

    assert re.fullmatch(SLUG_DATE + r"\.pdf", report_file_name(document, "pdf"))
    assert report_file_name(document, "md") == f"startup-validation_{file_slug(document.meta.idea_title)}_2026-11-16.md"


def test_a_hostile_idea_title_cannot_reach_the_download_header(monkeypatch: pytest.MonkeyPatch, build, fonts: Path) -> None:
    use_writer(monkeypatch)
    result = synthetic_complete()
    hostile = result.model_copy(update={"idea": result.idea.model_copy(update={"idea_title": 'Evil"; x=1 Set-Cookie: a'})})
    client = build(hostile)
    run_id = finished_run(client)
    generate(client, run_id)

    for suffix, extension in (("/pdf", "pdf"), ("/markdown", "md")):
        disposition = client.get(report_path(run_id, suffix)).headers["content-disposition"]
        assert disposition.startswith('attachment; filename="startup-validation_evil-x-1-set-cookie-a_')
        assert disposition.endswith(f'.{extension}"') and "\r" not in disposition and disposition.count('"') == 2


def test_deleting_the_report_keeps_the_run(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    generate(client, run_id)

    first = client.delete(report_path(run_id))
    second = client.delete(report_path(run_id))

    assert first.status_code == 204 and first.content == b""
    assert second.status_code == 204
    assert detail(client, run_id)["report"] == NO_REPORT
    assert client.get(report_path(run_id)).status_code == 404
    stored = row_of(client, run_id)
    assert (stored["report_json"], stored["report_fingerprint"], stored["report_generated_at"]) == (None, None, None)
    assert stored["result_json"] is not None


def test_deleting_the_run_removes_its_report(monkeypatch: pytest.MonkeyPatch, client: TestClient, tmp_path: Path) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    generate(client, run_id)

    assert client.delete(f"{RUNS}/{run_id}").status_code == 204

    assert error_of(client.get(report_path(run_id)))["code"] == "run_not_found"
    with closing(sqlite3.connect(tmp_path / "runs.db")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs WHERE id = ?", (run_id,)).fetchone()[0] == 0


def test_a_configured_key_in_the_report_is_never_stored_or_served(monkeypatch: pytest.MonkeyPatch, build, tmp_path: Path) -> None:
    leaky = json.loads(json.dumps(DRAFT))
    leaky["overview"][0]["text"] = f"The founder pasted {SECRET} into the idea by mistake."
    use_writer(monkeypatch, leaky)
    client = build(secrets=(SECRET,))
    run_id = finished_run(client)

    body = generate(client, run_id)

    assert SECRET not in json.dumps(body)
    assert REDACTED in json.dumps(body)
    assert SECRET not in (tmp_path / "runs.db").read_bytes().decode("utf-8", "ignore")
    assert SECRET not in client.get(report_path(run_id, "/markdown")).text


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        (json.dumps({"schema_version": 99, "title": "Later"}), MSG_NEWER_REPORT),
        ("{not json", MSG_UNREADABLE_REPORT),
        (json.dumps({"schema_version": 1, "title": "Half"}), MSG_UNREADABLE_REPORT),
    ],
)
def test_a_stored_report_this_version_cannot_read_is_refused_plainly_and_can_be_replaced(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, stored: str, message: str
) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    client.app.state.run_manager._store.update(run_id, report_json=stored, report_fingerprint="x", report_generated_at="y")

    for suffix in ("", "/pdf", "/markdown"):
        response = client.get(report_path(run_id, suffix))
        assert response.status_code == 404
        assert error_of(response) == {"code": "report_not_found", "message": message}
    assert detail(client, run_id)["report"] == NO_REPORT

    replaced = generate(client, run_id)

    assert replaced["schema_version"] == 1
    assert detail(client, run_id)["report"]["exists"] is True


def test_a_partial_run_gets_a_report_that_lists_what_is_missing(monkeypatch: pytest.MonkeyPatch, build) -> None:
    use_writer(monkeypatch)
    client = build(synthetic_partial())
    run_id = finished_run(client)

    body = generate(client, run_id)

    assert body["meta"]["run_status"] == "partial"
    assert {"market", "gtm"} <= {entry["id"] for entry in body["meta"]["sections_missing"]}


def test_the_existing_markdown_export_is_unchanged(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    use_writer(monkeypatch)
    run_id = finished_run(client)
    before = client.get(f"{RUNS}/{run_id}/report.md")

    generate(client, run_id)
    after = client.get(f"{RUNS}/{run_id}/report.md")

    run = RunDetail.model_validate(detail(client, run_id))
    assert before.status_code == after.status_code == 200
    assert after.content == before.content
    assert after.text == report_markdown(run.result, full=True)
    assert after.headers["content-disposition"] == before.headers["content-disposition"] == (
        'attachment; filename="validation_report.md"'
    )


def test_meta_describes_the_report_and_the_profiles(client: TestClient, no_fonts: Path) -> None:
    response = client.get("/api/meta")
    body = response.json()

    assert body["report"] == {"available": True, "pdf_available": False, "time_limit_s": 60.0}
    assert body["profiles"] == {"query_profile": "v1", "prompt_profile": "v1", "app_version": APP_VERSION}
    assert str(no_fonts) not in response.text and "fonts" not in json.dumps(body["report"])


def test_meta_says_the_pdf_is_available_once_the_fonts_are_installed(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, fonts: Path
) -> None:
    monkeypatch.setenv("REPORT_TIME_LIMIT_S", "90")

    body = client.get("/api/meta").json()

    assert body["report"] == {"available": True, "pdf_available": True, "time_limit_s": 90.0}


def test_the_openapi_schema_lists_the_five_report_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths[f"{RUNS}/{{run_id}}/report"]) == {"post", "get", "delete"}
    assert set(paths[f"{RUNS}/{{run_id}}/report/pdf"]) == {"get"}
    assert set(paths[f"{RUNS}/{{run_id}}/report/markdown"]) == {"get"}
    assert set(paths[f"{RUNS}/{{run_id}}/report.md"]) == {"get"}
    assert "application/pdf" in paths[f"{RUNS}/{{run_id}}/report/pdf"]["get"]["responses"]["200"]["content"]
    assert {"404", "409", "422", "503"} <= set(paths[f"{RUNS}/{{run_id}}/report"]["post"]["responses"])
    assert {"404", "422", "500"} <= set(paths[f"{RUNS}/{{run_id}}/report/pdf"]["get"]["responses"])
