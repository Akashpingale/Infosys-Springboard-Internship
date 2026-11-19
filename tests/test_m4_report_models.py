import json
import subprocess
import sys

import pytest
from pydantic import TypeAdapter, ValidationError

from models.report import (
    MSG_NEWER_REPORT,
    MSG_UNREADABLE_REPORT,
    REPORT_SCHEMA_VERSION,
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    FactsBlock,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    ReportItem,
    ReportMeta,
    ReportVersionError,
    SubheadingBlock,
    TableBlock,
    read_report,
)
from tests.m4_report_fixtures_synthetic import ROOT, SYNTHETIC_RESULTS, full_document

BLOCKS = TypeAdapter(ReportBlock)


def meta(**changes: object) -> dict:
    return {"run_id": "r1", "generated_at": "2026-11-16T10:00:00+00:00", "run_status": "complete", "idea_title": "Idea",
            "industry": "Other", "app_version": "0.1.0", **changes}


def document(**changes: object) -> dict:
    return {"title": "Startup validation report", "subtitle": "Idea", "meta": meta(), **changes}


def test_a_minimal_document_starts_at_schema_version_1() -> None:
    parsed = ReportDocument.model_validate(document())
    assert parsed.schema_version == REPORT_SCHEMA_VERSION == 1
    assert parsed.meta.narrative_status == "skipped"
    assert parsed.meta.consistency.checks == [] and parsed.sections == [] and parsed.bibliography == []


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        ({"type": "paragraph", "text": "A", "basis": "sourced", "cites": [3, 5]}, ParagraphBlock),
        ({"type": "bullets", "items": [{"text": "A", "basis": "assumption", "cites": []}]}, BulletsBlock),
        ({"type": "table", "caption": "C", "columns": ["Segment", "Priority"], "rows": [["A", "Priority"]],
          "col_align": ["left", "left"]}, TableBlock),
        ({"type": "callout", "kind": "caveat", "text": "A"}, CalloutBlock),
        ({"type": "facts", "pairs": [{"label": "L", "value": "V"}]}, FactsBlock),
        ({"type": "subheading", "text": "A"}, SubheadingBlock),
    ],
)
def test_each_block_type_is_read_by_its_type(data: dict, kind: type) -> None:
    block = BLOCKS.validate_python(data)
    dumped = BLOCKS.dump_python(block, mode="json")
    assert isinstance(block, kind)
    assert {key: dumped[key] for key in data} == data


@pytest.mark.parametrize(
    "data",
    [
        {"type": "chart", "text": "A"},
        {"type": "paragraph", "text": "A", "basis": "proven"},
        {"type": "callout", "kind": "alarm", "text": "A"},
        {"type": "table", "caption": "C", "columns": ["A", "B"], "rows": [["only one"]]},
        {"type": "table", "caption": "C", "columns": ["A"], "rows": [["x"]], "col_align": ["left", "right"]},
        {"type": "table", "caption": "C", "columns": ["A"], "rows": [["x"]], "row_cites": [[1], [2]]},
        {"type": "table", "caption": "C", "columns": ["A"], "rows": [["x"]], "col_align": ["middle"]},
    ],
)
def test_invalid_blocks_are_rejected(data: dict) -> None:
    with pytest.raises(ValidationError):
        BLOCKS.validate_python(data)


def test_the_internal_source_keys_never_leave_the_model() -> None:
    item = ReportItem(text="A", keys=["market:S1"])
    paragraph = ParagraphBlock(text="A", keys=["market:S1"])
    table = TableBlock(caption="C", columns=["A"], rows=[["x"]], row_keys=[["market:S1"]])
    assert "keys" not in item.model_dump() and "keys" not in paragraph.model_dump()
    assert "row_keys" not in table.model_dump()


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.org/file", "data:text/html,x", "example.org"])
def test_a_bibliography_link_must_be_http_or_https(url: str) -> None:
    with pytest.raises(ValidationError):
        BibEntry(number=1, title="T", url=url)


def test_a_bibliography_entry_may_have_no_link() -> None:
    assert BibEntry(number=1, title="Search engine summary", url=None, has_page=False).url is None
    assert BibEntry(number=2, title="T", url="https://example.org/page").url == "https://example.org/page"
    with pytest.raises(ValidationError):
        BibEntry(number=0, title="T")


@pytest.mark.parametrize("changes", [{"narrative_status": "maybe"}, {"run_status": "done"}])
def test_meta_values_are_restricted(changes: dict) -> None:
    with pytest.raises(ValidationError):
        ReportMeta.model_validate(meta(**changes))


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_a_built_document_round_trips_through_json(name: str) -> None:
    built = full_document(SYNTHETIC_RESULTS[name]())
    data = json.loads(built.model_dump_json())
    assert ReportDocument.model_validate(data).model_dump(mode="json") == data
    assert read_report(data) == ReportDocument.model_validate(data)
    assert '"keys"' not in built.model_dump_json() and '"row_keys"' not in built.model_dump_json()


def test_a_newer_stored_report_is_refused_with_a_plain_message() -> None:
    with pytest.raises(ReportVersionError) as info:
        read_report(document(schema_version=REPORT_SCHEMA_VERSION + 1))
    assert str(info.value) == MSG_NEWER_REPORT


@pytest.mark.parametrize("data", [None, [], "text", {"schema_version": "1"}, {"schema_version": True}, document(meta={})])
def test_an_unreadable_stored_report_is_refused_without_a_crash(data: object) -> None:
    with pytest.raises(ReportVersionError) as info:
        read_report(data)
    assert str(info.value) == MSG_UNREADABLE_REPORT


def test_a_stored_report_of_this_version_is_read() -> None:
    assert read_report(document()).subtitle == "Idea"
    assert read_report({key: value for key, value in document().items()}).schema_version == 1


def test_the_report_models_import_first_without_a_cycle() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "-c", "import models.report; import models.schemas"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
