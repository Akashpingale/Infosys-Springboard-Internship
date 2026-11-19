import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from agents import report_agent
from agents.report_agent import (
    CLOSING_CAVEAT,
    HEADING_ACTIONS,
    HEADING_INSIGHTS,
    MSG_NARRATIVE_FAILED,
    OVERVIEW_CHARS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    VERDICT_PHRASES,
    VERIFY_WHY,
    build_prompt,
    build_report,
    check_narrative,
    narrative_digest,
    report_fingerprint,
    step_text,
)
from agents.report_sections import CATALOGUE_IDS, NOT_INCLUDED, REASON_NO_STRATEGY, stage_names, unfinished_stages
from agents.strategy_context import ref_prefix
from config import get_settings
from models.api import RunDetail
from models.report import (
    BulletsBlock,
    CalloutBlock,
    ParagraphBlock,
    ReportDocument,
    ReportNarrativeDraft,
    SubheadingBlock,
    read_report,
)
from models.schemas import PipelineResult, StrategyConstraints, Usage, Versions
from tests.m4_report_fixtures_synthetic import (
    GENERATED_AT,
    ROOT,
    RUN_ID,
    SYNTHETIC_RESULTS,
    synthetic_complete,
    synthetic_minimal,
    synthetic_no_strategy,
    synthetic_partial,
)
from tests.pipeline_fakes import PIPELINE_SUBMISSION
from tests.test_m3_strict_schema import RANGE_KEYWORDS
from tests.test_m2_groq_structured import schema_nodes
from tests.test_m4_usage_versions import counted, server_error, use_providers
from utils import deadline, groq_client
from utils.errors import LLMAPIError, LLMConfigError, ReportUnavailableError

SAVED = sorted(path for path in (ROOT / "docs").glob("test_runs*/*.json") if path.name != "run_summary.json")
LIVE = [ROOT / "web" / "src" / "test" / "liveAgritech.json", ROOT / "web" / "src" / "test" / "liveFintech.json"]
FAKE_TAVILY_SHAPE = "tvly-" + "PLANTEDFAKE" + "0123456789"

DRAFT: dict[str, Any] = {
    "overview": [
        {
            "text": "CropScan is a phone app that detects crop diseases from a photo for small farmers in India.",
            "basis": "user_provided",
            "based_on": ["IDEA.1", "IDEA.3", "IDEA.4"],
        },
        {
            "text": "The evidence shows that farmers lose crops to late diagnosis, but it cannot confirm the size of this "
            "idea's own market.",
            "basis": "ai_interpretation",
            "based_on": ["MKT.5", "MKT.9"],
        },
    ],
    "key_insights": [
        {
            "text": "The priority segment of smallholder farmers lines up with the gap in treatment advice.",
            "basis": "ai_interpretation",
            "based_on": ["MKT.16", "CMP.25"],
        },
        {
            "text": "A free app already reaches farmers, so keeping them is the main risk for the first release.",
            "basis": "ai_interpretation",
            "based_on": ["MKT.18", "RSK.1"],
        },
        {
            "text": "Local language support appears in the competitor evidence and in the planned features.",
            "basis": "ai_interpretation",
            "based_on": ["CMP.21", "MVP.3"],
        },
    ],
    "next_steps": [
        {
            "action": "Interview pilot farmers about why they would switch from the free app.",
            "why": "The highest risk is that farmers stay with the free app.",
            "based_on": ["RSK.1"],
        },
        {
            "action": "Test the diagnosis on poor photos before launch.",
            "why": "Wrong diagnosis on poor photos is a high-severity risk.",
            "based_on": ["RSK.2", "MVP.1"],
        },
        {
            "action": "Start with short demo videos on a messaging app.",
            "why": "It is the channel ranked first in the plan.",
            "based_on": ["GTM.2"],
        },
    ],
    "closing_caveat": "This report interprets evidence and does not predict results.",
}


class FakeWriter:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, str]] = []
        self.time_left: list[float | None] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        self.time_left.append(deadline.time_left())
        outcome = self.outcomes[min(len(self.calls), len(self.outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome if isinstance(outcome, str) else json.dumps(outcome)


def use_writer(monkeypatch: pytest.MonkeyPatch, *outcomes: Any) -> FakeWriter:
    writer = FakeWriter(*(outcomes or (DRAFT,)))
    monkeypatch.setattr(report_agent, "generate_json", writer)
    return writer


def run_of(result: PipelineResult | None, *, state: str = "done", constraints: StrategyConstraints | None = None) -> RunDetail:
    return RunDetail(
        id=RUN_ID,
        title="CropScan",
        industry="Agriculture",
        state=state,
        created_at=GENERATED_AT,
        stages=[],
        submission=PIPELINE_SUBMISSION,
        result=result,
        constraints=constraints,
    )


def report_of(result: PipelineResult, **options: Any) -> ReportDocument:
    return build_report(run_of(result), generated_at=GENERATED_AT, **options)


def section(document: ReportDocument, section_id: str):
    return next(entry for entry in [*document.sections, *document.appendix_sections] if entry.id == section_id)


def narrative_blocks(document: ReportDocument) -> list[Any]:
    return [block for entry in document.sections for block in entry.blocks if getattr(block, "narrative", False)]


def assert_checked(document: ReportDocument) -> None:
    report = document.meta.consistency
    assert (report.passed_count, report.total_count) == (12, 12), [(c.id, c.detail) for c in report.checks if not c.passed]
    assert [entry.id for entry in [*document.sections, *document.appendix_sections]] == list(CATALOGUE_IDS)


def draft_with(**changes: Any) -> ReportNarrativeDraft:
    data = copy.deepcopy(DRAFT)
    data.update(changes)
    return ReportNarrativeDraft.model_validate(data)


def statement(text: str, basis: str = "ai_interpretation", based_on: list[str] | None = None) -> dict[str, Any]:
    return {"text": text, "basis": basis, "based_on": ["MKT.5"] if based_on is None else based_on}


def step(action: str, why: str = "It tests the biggest unknown.", based_on: list[str] | None = None) -> dict[str, Any]:
    return {"action": action, "why": why, "based_on": ["RSK.1"] if based_on is None else based_on}


def checked(result: PipelineResult, **changes: Any):
    return check_narrative(draft_with(**changes), narrative_digest(result), result)


def load(path: Path) -> PipelineResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PipelineResult.model_validate(data.get("result", data) if "stages" in data else data)


def test_a_complete_run_gets_every_section_and_a_checked_narrative(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = use_writer(monkeypatch)
    document = report_of(synthetic_complete())
    assert len(writer.calls) == 1
    assert_checked(document)
    meta = document.meta
    assert meta.narrative_status == "ok"
    assert meta.prompt_version == PROMPT_VERSION
    assert meta.sections_missing == []
    assert meta.sections_included == list(CATALOGUE_IDS)
    summary = section(document, "executive_summary").blocks
    assert [block.text for block in summary[:2]] == [entry["text"] for entry in DRAFT["overview"]]
    assert all(isinstance(block, ParagraphBlock) and block.narrative for block in summary[:2])
    assert isinstance(summary[2], BulletsBlock) and not summary[2].narrative
    assert [item.text for item in summary[2].items] == [line.text for line in synthetic_complete().executive_summary]
    assert summary[3] == SubheadingBlock(text=HEADING_INSIGHTS)
    assert [item.text for item in summary[4].items] == [entry["text"] for entry in DRAFT["key_insights"]]
    assert summary[5] == CalloutBlock(kind="caveat", text=CLOSING_CAVEAT)
    steps = section(document, "next_steps").blocks
    assert steps[0] == SubheadingBlock(text=HEADING_ACTIONS)
    assert [item.text for item in steps[1].items] == [
        f"{entry['action']} Why: {entry['why']}" for entry in DRAFT["next_steps"]
    ]
    assert steps[2] == SubheadingBlock(text="What to verify")


def test_narrative_statements_carry_citations_from_the_facts_they_cite(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    document = report_of(synthetic_complete())
    summary = section(document, "executive_summary").blocks
    assert summary[0].cites == []
    assert summary[1].cites
    numbers = {entry.number: entry for entry in document.bibliography}
    assert all(number in numbers for block in narrative_blocks(document) for number in getattr(block, "cites", []))
    assert all("executive_summary" in numbers[number].cited_in for number in summary[1].cites)


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_every_synthetic_fixture_builds_a_checked_report(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    use_writer(monkeypatch)
    document = report_of(SYNTHETIC_RESULTS[name]())
    assert_checked(document)
    assert document.meta.narrative_status == "ok"
    assert read_report(document.model_dump(mode="json")) == document


@pytest.mark.parametrize("path", [*SAVED, *LIVE], ids=lambda path: path.name)
def test_every_stored_result_builds_a_checked_report(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    use_writer(monkeypatch)
    result = load(path)
    if result.status == "failed":
        with pytest.raises(ReportUnavailableError):
            report_of(result)
        return
    document = report_of(result)
    assert_checked(document)
    assert document.meta.narrative_status == "ok"


def test_a_partial_run_explains_what_did_not_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    result = synthetic_partial()
    document = report_of(result)
    assert_checked(document)
    missing = {entry.id: entry.reason for entry in document.meta.sections_missing}
    assert set(missing) == {"market", "gtm"}
    for section_id, reason in missing.items():
        assert NOT_INCLUDED.format(reason=reason) in [block.text for block in section(document, section_id).blocks]
    unfinished = stage_names(unfinished_stages(result))
    warnings = [block.text for block in section(document, "cover").blocks if isinstance(block, CalloutBlock)]
    assert len(unfinished) == 2 and any(all(name in text for name in unfinished) for text in warnings)
    actions = [item.text for item in section(document, "next_steps").blocks[1].items]
    assert actions[:2] == [step_text(report_agent.Step(entry["action"], entry["why"], None, [])) for entry in DRAFT["next_steps"][:2]]
    assert actions[2] == f"{result.verify_next[0].text} Why: {VERIFY_WHY}"


def test_a_run_without_strategy_fills_next_steps_from_what_to_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    result = synthetic_no_strategy()
    document = report_of(result)
    assert_checked(document)
    missing = {entry.id: entry.reason for entry in document.meta.sections_missing}
    assert missing == {section_id: REASON_NO_STRATEGY for section_id in ("swot", "risks", "mvp", "gtm")}
    items = section(document, "next_steps").blocks[1].items
    assert [item.text for item in items] == [f"{entry.text} Why: {VERIFY_WHY}" for entry in result.verify_next[:3]]
    assert all(item.basis is None for item in items)
    digest = narrative_digest(result)
    assert not {ref_prefix(fact.ref) for fact in digest.facts} & {"RSK", "MVP", "GTM"}


def test_a_minimal_run_keeps_next_steps_missing_when_nothing_can_be_linked(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    document = report_of(synthetic_minimal())
    assert_checked(document)
    assert "next_steps" in {entry.id for entry in document.meta.sections_missing}
    assert "executive_summary" in document.meta.sections_included
    overview = section(document, "executive_summary").blocks[0]
    assert overview.text == DRAFT["overview"][0]["text"] and overview.basis == "user_provided"
    second = section(document, "executive_summary").blocks[1]
    assert second.narrative and second.basis == "assumption" and second.cites == []


@pytest.mark.parametrize("failure", [LLMAPIError(), LLMConfigError()], ids=["provider", "not_configured"])
def test_a_failed_narrative_still_produces_the_report(monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    use_writer(monkeypatch, failure)
    failed = report_of(synthetic_complete())
    skipped = report_of(synthetic_complete(), narrative=False)
    assert_checked(failed)
    assert failed.meta.narrative_status == "failed"
    assert failed.meta.prompt_version == PROMPT_VERSION
    for section_id in ("executive_summary", "next_steps"):
        blocks = section(failed, section_id).blocks
        assert blocks[0] == CalloutBlock(kind="warning", text=MSG_NARRATIVE_FAILED)
        assert blocks[1:] == section(skipped, section_id).blocks
    others = [entry for entry in failed.sections if entry.id not in ("executive_summary", "next_steps")]
    assert others == [entry for entry in skipped.sections if entry.id not in ("executive_summary", "next_steps")]
    assert narrative_blocks(failed) == []


def test_invalid_narrative_output_after_the_retry_is_a_narrative_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = use_writer(monkeypatch, "not json", {"overview": "not a list"})
    document = report_of(synthetic_complete())
    assert len(writer.calls) == 2
    assert document.meta.narrative_status == "failed"
    assert_checked(document)


def test_a_sourced_basis_from_the_model_is_rejected_by_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    sourced = copy.deepcopy(DRAFT)
    sourced["overview"][0]["basis"] = "sourced"
    writer = use_writer(monkeypatch, sourced, sourced)
    document = report_of(synthetic_complete())
    assert len(writer.calls) == 2
    assert document.meta.narrative_status == "failed"


def test_a_valid_reply_after_the_retry_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = use_writer(monkeypatch, "not json", DRAFT)
    document = report_of(synthetic_complete())
    assert len(writer.calls) == 2
    assert document.meta.narrative_status == "ok"


def test_without_the_narrative_no_ai_request_is_made(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = use_writer(monkeypatch)
    document = report_of(synthetic_complete(), narrative=False)
    assert writer.calls == []
    assert document.meta.narrative_status == "skipped"
    assert document.meta.prompt_version is None
    assert narrative_blocks(document) == []
    assert_checked(document)


def test_the_narrative_call_runs_under_the_report_time_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORT_TIME_LIMIT_S", raising=False)
    writer = use_writer(monkeypatch)
    report_of(synthetic_complete())
    assert 59.0 < writer.time_left[0] <= 60.0
    monkeypatch.setenv("REPORT_TIME_LIMIT_S", "25")
    report_of(synthetic_complete())
    assert 24.0 < writer.time_left[1] <= 25.0
    assert deadline.time_left() is None


@pytest.mark.parametrize(("raw", "expected"), [(None, 60.0), ("20", 20.0), ("90", 90.0), ("600", 600.0), ("19", 60.0),
                                               ("601", 60.0), ("soon", 60.0)])
def test_the_report_time_limit_setting_is_bounded(monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: float) -> None:
    if raw is None:
        monkeypatch.delenv("REPORT_TIME_LIMIT_S", raising=False)
    else:
        monkeypatch.setenv("REPORT_TIME_LIMIT_S", raw)
    assert get_settings().report_time_limit_s == expected


def test_the_env_example_documents_the_report_time_limit() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "# REPORT_TIME_LIMIT_S=60" in lines


def test_reaching_the_report_time_limit_is_a_narrative_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, json.dumps(DRAFT))
    ticks = iter([0.0, 1000.0])
    monkeypatch.setattr(deadline, "clock", lambda: next(ticks, 1000.0))
    document = report_of(synthetic_complete())
    assert document.meta.narrative_status == "failed"
    assert gemini.calls == 0 and network.tavily_calls == 0


def test_the_report_makes_exactly_one_ai_request_and_no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, json.dumps(DRAFT))
    documents: list[ReportDocument] = []
    assert counted(lambda: documents.append(report_of(synthetic_complete()))) == (1, 0)
    assert gemini.calls == 1 and network.tavily_calls == 0 and network.groq_calls == 0
    assert documents[0].meta.narrative_status == "ok"


def test_existing_client_retries_are_the_only_extra_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, server_error(), json.dumps(DRAFT))
    assert counted(lambda: report_of(synthetic_complete())) == (2, 0)
    assert gemini.calls == 2 and network.tavily_calls == 0


def test_a_report_without_the_narrative_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini, network = use_providers(monkeypatch, json.dumps(DRAFT))
    assert counted(lambda: report_of(synthetic_complete(), narrative=False)) == (0, 0)
    assert gemini.calls == 0 and network.tavily_calls == 0


@pytest.mark.parametrize("state", ["queued", "running", "failed", "cancelled"])
def test_a_run_that_is_not_done_has_no_report(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    writer = use_writer(monkeypatch)
    with pytest.raises(ReportUnavailableError) as raised:
        build_report(run_of(synthetic_complete(), state=state))
    assert (raised.value.code, raised.value.status_code) == ("report_unavailable", 409)
    assert writer.calls == []


def test_a_done_run_without_a_usable_result_has_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = use_writer(monkeypatch)
    with pytest.raises(ReportUnavailableError):
        build_report(run_of(None))
    with pytest.raises(ReportUnavailableError):
        build_report(run_of(synthetic_complete().model_copy(update={"status": "failed"})))
    assert writer.calls == []


def test_the_fingerprint_is_the_canonical_json_of_result_and_constraints() -> None:
    result = synthetic_complete()
    constraints = StrategyConstraints(team_size=2)
    payload = {
        "result": result.model_dump(mode="json", exclude={"usage", "versions"}),
        "constraints": constraints.model_dump(mode="json"),
    }
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert report_fingerprint(result, constraints) == expected
    assert report_fingerprint(result, None) != expected
    assert report_fingerprint(PipelineResult.model_validate_json(result.model_dump_json()), constraints) == expected


def test_usage_and_versions_never_make_the_fingerprint_change() -> None:
    result = synthetic_complete()
    counted_result = result.model_copy(update={
        "usage": Usage(llm_calls=9, search_calls=4),
        "versions": Versions(query_profile="v1", prompt_profile="v1", app_version="9.9.9"),
    })
    assert report_fingerprint(counted_result, None) == report_fingerprint(result.model_copy(update={"usage": None, "versions": None}), None)


def test_adding_strategy_changes_the_fingerprint_and_the_report_stores_it(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    without, with_strategy = synthetic_no_strategy(), synthetic_complete()
    assert report_fingerprint(without, None) != report_fingerprint(with_strategy, None)
    constraints = StrategyConstraints(team_size=2, months_to_mvp=4)
    document = build_report(run_of(with_strategy, constraints=constraints), generated_at=GENERATED_AT)
    assert document.meta.source_fingerprint == report_fingerprint(with_strategy, constraints)
    assert len(document.meta.source_fingerprint) == 64


def test_the_prompt_is_the_appendix_a1_prompt_over_the_report_facts() -> None:
    result = synthetic_complete()
    system, user = build_prompt(narrative_digest(result))
    assert system == SYSTEM_PROMPT
    assert "Role: editor writing the summary section of a startup validation report for a founder and a mentor." in system
    assert "Do not use words such as viable, not viable, proceed, abandon, promising or doomed." in system
    assert "Never use sourced." in system
    assert user.startswith("The facts cover the idea (IDEA), constraints (CON), market (MKT), competitors (CMP)")
    assert "4. closing_caveat: one sentence" in user
    prefixes = {ref_prefix(fact.ref) for fact in narrative_digest(result).facts}
    assert prefixes == {"IDEA", "CON", "MKT", "CMP", "RSK", "MVP", "GTM", "VER"}
    assert "[GTM.2]" in user and "[VER.1]" in user and "[SUM." not in user and "[SWT." not in user and "[NTC." not in user


def test_the_digest_keeps_within_its_cap_by_dropping_the_least_needed_facts() -> None:
    result = synthetic_complete()
    full = narrative_digest(result)
    small = narrative_digest(result, max_chars=len(full.text) - 150)
    assert small.dropped and small.fits
    assert {fact.kind for fact in full.facts if fact.ref in small.dropped} <= {"broader_market", "trend", "query_used", "demand"}


def test_invalid_refs_are_removed_and_unlinked_statements_become_assumptions() -> None:
    narrative = checked(synthetic_complete(), key_insights=[
        statement("Smallholder farmers feel the losses most.", based_on=["MKT.16", "MKT.999"]),
        statement("Cooperatives may adopt slowly.", based_on=["XYZ.1"]),
        statement("Farmers could pay for faster advice.", basis="user_provided", based_on=["MKT.5"]),
    ])
    first, second, third = narrative.insights
    assert first.basis == "ai_interpretation" and first.keys == []
    assert second.basis == "assumption" and second.keys == []
    assert third.basis == "ai_interpretation" and third.keys == ["market:S5"]


def test_a_statement_from_the_founder_keeps_its_basis() -> None:
    narrative = checked(synthetic_complete())
    assert narrative.overview[0].basis == "user_provided"
    assert all(block.basis != "sourced" for block in narrative.overview)


def test_unsupported_figures_are_removed_and_supported_ones_kept() -> None:
    narrative = checked(synthetic_complete(), key_insights=[
        statement("The market is worth USD 9 billion.", based_on=["MKT.8"]),
        statement("A third of farmers would pay 40% more.", based_on=["MKT.5"]),
        statement("The stated market is USD 1.8 billion.", based_on=["MKT.8"]),
    ], next_steps=[step("Raise USD 50,000 for the pilot.", based_on=["RSK.4"]), *DRAFT["next_steps"]])
    assert [item.text for item in narrative.insights] == ["The stated market is USD 1.8 billion."]
    assert all("50,000" not in entry.action for entry in narrative.steps)
    assert any("figure" in warning for warning in narrative.warnings)


def test_overclaims_are_removed() -> None:
    narrative = checked(synthetic_complete(), key_insights=[
        statement("Farmers are guaranteed to switch."),
        statement("There is no competition for treatment advice."),
        statement("Treatment advice is a possible gap."),
    ], next_steps=[step("Launch now because it can't fail."), *DRAFT["next_steps"]])
    assert [item.text for item in narrative.insights] == ["Treatment advice is a possible gap."]
    assert all("fail" not in entry.action for entry in narrative.steps)


@pytest.mark.parametrize("phrase", [*VERDICT_PHRASES, "you should proceed", "do not proceed", "abandoned", "proceeding"])
def test_verdict_language_is_removed(phrase: str) -> None:
    text = f"On this evidence the idea is {phrase}."
    narrative = checked(synthetic_complete(), key_insights=[statement(text), *DRAFT["key_insights"]],
                        next_steps=[step(f"Decide that it is {phrase}."), *DRAFT["next_steps"]])
    assert text not in [item.text for item in narrative.insights]
    assert len(narrative.insights) == 3
    assert [entry.action for entry in narrative.steps] == [entry["action"] for entry in DRAFT["next_steps"]]
    assert any("verdict" in warning for warning in narrative.warnings)


def test_words_that_only_start_like_a_verdict_word_are_kept() -> None:
    kept = ["Viability tests come later.", "The promise of faster advice draws farmers."]
    narrative = checked(synthetic_complete(), key_insights=[statement(text) for text in kept])
    assert [item.text for item in narrative.insights] == kept


def test_near_duplicates_keep_the_first() -> None:
    first = "Local language support appears in the competitor evidence and the planned features."
    narrative = checked(synthetic_complete(), key_insights=[
        statement(first), statement(first.replace(".", " too.")), *DRAFT["key_insights"][:2],
    ], next_steps=[*DRAFT["next_steps"], step(DRAFT["next_steps"][0]["action"])])
    assert [item.text for item in narrative.insights] == [first, *(entry["text"] for entry in DRAFT["key_insights"][:2])]
    assert len(narrative.steps) == 3


def test_counts_and_lengths_are_enforced() -> None:
    long_text = "Farmers lose crops when diseases are spotted late, " * 20
    narrative = checked(
        synthetic_complete(),
        overview=[statement(long_text.strip()), statement("Second paragraph."), statement("Third paragraph.")],
        key_insights=[statement(f"Insight about {word} and the market.") for word in
                      ("farmers", "cooperatives", "retailers", "photos", "languages", "prices", "videos")],
        next_steps=[step(f"Test the assumption about {word} with the pilot.", based_on=["RSK.1"]) for word in
                    ("farmers", "cooperatives", "retailers", "photos", "languages", "prices", "videos", "drones")],
    )
    assert len(narrative.overview) == 2
    assert len(narrative.overview[0].text) <= OVERVIEW_CHARS
    assert narrative.overview[0].text.endswith("...")
    assert len(narrative.insights) == 5
    assert len(narrative.steps) == 6


def test_next_steps_must_cite_a_finding() -> None:
    result = synthetic_complete()
    narrative = checked(result, next_steps=[
        step("Write down the idea again.", based_on=["IDEA.1"]),
        step("Ask the team about time.", based_on=["CON.1"]),
        step("Check the main risk with farmers.", based_on=["RSK.1"]),
        step("Look at the verify list.", based_on=["VER.2"]),
    ])
    actions = [entry.action for entry in narrative.steps]
    assert actions[:2] == ["Check the main risk with farmers.", "Look at the verify list."]
    assert actions[2] == result.verify_next[0].text
    assert any("not linked" in warning for warning in narrative.warnings)


def test_missing_next_steps_are_filled_from_what_to_verify_and_the_first_channel() -> None:
    result = synthetic_complete()
    narrative = checked(result, next_steps=[])
    assert [entry.action for entry in narrative.steps] == [entry.text for entry in result.verify_next[:3]]
    channel_only = result.model_copy(update={"verify_next": []})
    filled = checked(channel_only, next_steps=[])
    channel = next(entry for entry in result.gtm.channels if entry.start_here)
    assert [entry.action for entry in filled.steps] == [f"Run the first experiment for {channel.name}: {channel.first_experiment}"]
    assert filled.steps[0].basis == channel.basis
    assert any("fewer than 3" in warning for warning in filled.warnings)


def test_a_fill_never_repeats_a_step_the_model_wrote() -> None:
    result = synthetic_complete()
    first = result.verify_next[0].text
    narrative = checked(result, next_steps=[step(first, based_on=["VER.1"])])
    actions = [entry.action for entry in narrative.steps]
    assert actions == [first, result.verify_next[1].text, result.verify_next[2].text]


def test_the_closing_caveat_is_fixed_text_written_by_code(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch, {**DRAFT, "closing_caveat": "This idea will succeed with the right team."})
    document = report_of(synthetic_complete())
    texts = [getattr(block, "text", "") for entry in document.sections for block in entry.blocks]
    assert CLOSING_CAVEAT in texts
    assert not any("right team" in text for text in texts)
    assert CLOSING_CAVEAT.count(".") == 1


def test_key_shaped_text_fails_the_narrative(monkeypatch: pytest.MonkeyPatch) -> None:
    planted = copy.deepcopy(DRAFT)
    planted["key_insights"][0]["text"] = f"Use the token {FAKE_TAVILY_SHAPE} for the pilot."
    use_writer(monkeypatch, planted)
    document = report_of(synthetic_complete())
    assert document.meta.narrative_status == "failed"
    assert FAKE_TAVILY_SHAPE not in document.model_dump_json()
    assert_checked(document)


def test_a_narrative_without_a_usable_overview_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch, {**DRAFT, "overview": [statement("The idea is promising.")]})
    document = report_of(synthetic_complete())
    assert document.meta.narrative_status == "failed"
    assert section(document, "executive_summary").blocks[0] == CalloutBlock(kind="warning", text=MSG_NARRATIVE_FAILED)


def test_control_characters_are_removed_from_narrative_text() -> None:
    narrative = checked(synthetic_complete(), key_insights=[statement("Farmers\x00 lose\x1b crops\n late."), *DRAFT["key_insights"]])
    assert narrative.insights[0].text == "Farmers lose crops late."


def test_the_draft_fits_the_groq_strict_schema() -> None:
    schema = groq_client.strict_schema(ReportNarrativeDraft)
    Draft202012Validator.check_schema(schema)
    for node in schema_nodes(schema):
        assert set(node) <= groq_client.STRICT_KEYWORDS, sorted(set(node) - groq_client.STRICT_KEYWORDS)
        if "properties" in node:
            assert node["required"] == list(node["properties"])
            assert node["additionalProperties"] is False
    enums = [node["properties"]["basis"]["enum"] for node in schema_nodes(schema) if "basis" in node.get("properties", {})]
    assert enums and all(sorted(enum) == ["ai_interpretation", "assumption", "user_provided"] for enum in enums)
    complete = ReportNarrativeDraft.model_validate(DRAFT).model_dump(mode="json")
    assert list(Draft202012Validator(schema).iter_errors(complete)) == []
    assert list(Draft202012Validator(schema).iter_errors({**complete, "verdict": "go"}))


def test_the_draft_leaves_counts_and_lengths_to_code() -> None:
    for node in schema_nodes(ReportNarrativeDraft.model_json_schema()):
        assert not set(node) & RANGE_KEYWORDS, sorted(set(node) & RANGE_KEYWORDS)


def test_the_report_never_holds_a_narrative_statement_labelled_sourced(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    for make in SYNTHETIC_RESULTS.values():
        document = report_of(make())
        for block in narrative_blocks(document):
            bases = [block.basis] if isinstance(block, ParagraphBlock) else [entry.basis for entry in block.items]
            assert "sourced" not in bases


def test_the_returned_document_round_trips_through_the_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    use_writer(monkeypatch)
    document = report_of(synthetic_complete())
    data = json.loads(document.model_dump_json())
    assert read_report(data) == document
    assert "keys" not in json.dumps(data)
