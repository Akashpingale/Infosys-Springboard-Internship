from collections import Counter

import pytest

from agents import derived, notices
from agents.derived import evidence_strength, executive_summary, strategy_sources, verify_next, with_derived_fields
from agents.gtm_agent import AUDIENCE_REPLACED, BUDGET_CONFLICT, NO_MVP, NO_SEGMENTS, PHASES_MISSING
from agents.gtm_agent import NO_SWOT as GTM_NO_SWOT
from agents.mvp_agent import FOUNDER_ADDED, OVER_CAPACITY, RATINGS_CLAMPED, TARGETS_REMOVED
from agents.mvp_agent import NO_SWOT as MVP_NO_SWOT
from agents.notices import STRATEGY_TITLES, build_notices, leaks, notice_for_error, notice_for_warning
from agents.strategy_checks import Repairs
from agents.swot_risk_agent import CONFIDENCE_LOWERED, EMPTY_REMOVED, FEWER_THAN_ASKED
from models.schemas import PipelineResult, StageError, StrategySourceKey
from orchestrator import SKIP_CANCELLED, SKIP_NO_ANALYSIS, SKIP_NO_TIME, STAGE_GTM, STAGE_MVP, STAGE_SWOT
from tests.test_m3_report import CONSTRAINTS, strategy_result, without_strategy
from utils.errors import LLMAPIError

SWOT_LABEL, MVP_LABEL, GTM_LABEL = (STRATEGY_TITLES[stage] for stage in (STAGE_SWOT, STAGE_MVP, STAGE_GTM))
STRATEGY_TOPICS = ["top_risk", "mvp_scope", "start_channel"]
TECHNICAL = ("MKT", "CMP", "RSK", "IDEA.", "CON.", "MVP.", "strategy_", "based_on", "digest", "[", "]")


@pytest.fixture
def complete(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    result = strategy_result(monkeypatch)
    assert result.status == "complete" and result.swot and result.mvp and result.gtm, "the fixture must be complete"
    return result


def key(source: StrategySourceKey) -> tuple[str, str]:
    return source.analysis, source.id


def expected_sources(sources) -> tuple[str | None, list[str]]:
    keys = list(dict.fromkeys(key(source) for source in sources))
    if not keys:
        return None, []
    counts = Counter(analysis for analysis, _ in keys)
    best = max(counts.values())
    analysis = next(analysis for analysis, _ in keys if counts[analysis] == best)
    return analysis, [source_id for name, source_id in keys if name == analysis]


def source_ids(result: PipelineResult, analysis: str) -> set[str]:
    return {source.id for source in getattr(result, analysis).sources}


def full_repairs() -> Repairs:
    return Repairs(
        refs_removed=["MKT.50"], to_assumption=1, to_interpretation=1, figures_removed=1, overclaims_removed=1,
        overclaim_phrases=["guaranteed"], duplicates_removed=1, cut={"strengths": 1}, shortened=1,
    )


def agent_warnings() -> list[str]:
    return [
        *full_repairs().warnings(),
        EMPTY_REMOVED.format(count="2 points"),
        CONFIDENCE_LOWERED.format(count="1 risk"),
        FEWER_THAN_ASKED.format(parts="threats 1 of at least 2"),
        MVP_NO_SWOT,
        "assumed a team of 2 people and 3 months to the first release because they were not given",
        OVER_CAPACITY.format(need="4", capacity="3.6"),
        RATINGS_CLAMPED.format(count="2 ratings"),
        FOUNDER_ADDED.format(count="1 feature", names="Voice notes"),
        TARGETS_REMOVED.format(count="1 metric"),
        "removed 2 links to risks that are not in the risk analysis (RSK.9, R3)",
        NO_MVP,
        GTM_NO_SWOT,
        NO_SEGMENTS,
        AUDIENCE_REPLACED,
        BUDGET_CONFLICT.format(count="2 channels", names="Radio farm shows, Village fairs"),
        PHASES_MISSING.format(count=2, total=3, names="Launch"),
        "removed 1 link to features that are not in the MVP recommendation (MVP.7)",
        "skipped because it needs at least one finished analysis.",
        "some future check changed positioning.for_whom[0] and S4",
    ]


# --- executive summary (Section 12.5) ----------------------------------------------------------


def test_summary_lines_are_added_only_when_strategy_exists(complete: PipelineResult) -> None:
    plain = without_strategy(complete)
    lines = executive_summary(complete)

    assert STRATEGY_TOPICS[0] not in [line.topic for line in executive_summary(plain)]
    assert lines[: len(executive_summary(plain))] == executive_summary(plain)
    assert [line.topic for line in lines[len(executive_summary(plain)):]] == STRATEGY_TOPICS
    assert derived.strategy_summary(plain) == [] and derived.strategy_verify_next(plain) == []


def test_the_summary_names_the_top_risk_the_first_release_and_the_start_channel(complete: PipelineResult) -> None:
    risk_line, mvp_line, channel_line = executive_summary(complete)[-3:]
    risk = complete.swot.risks[0]
    first = sorted((feature for feature in complete.mvp.features if feature.tier == "mvp"), key=lambda feature: feature.rank)
    start = next(channel for channel in complete.gtm.channels if channel.start_here)

    assert (risk.severity, risk.impact) == ("high", "high")
    assert risk_line.text == f"Main risk (high severity, {risk.category}): {risk.title}."
    assert risk_line.basis == risk.basis
    assert mvp_line.text == (
        f"First release, the top 3 of {len(first)} features: {first[0].name}, {first[1].name} and {first[2].name}."
    )
    assert channel_line.text == f"Go-to-market, start here: {start.name}." and channel_line.basis == start.basis


def test_each_summary_line_carries_the_inherited_sources(complete: PipelineResult) -> None:
    risk_line, mvp_line, channel_line = executive_summary(complete)[-3:]
    risk = complete.swot.risks[0]
    first = sorted((feature for feature in complete.mvp.features if feature.tier == "mvp"), key=lambda feature: feature.rank)[:3]
    start = next(channel for channel in complete.gtm.channels if channel.start_here)

    for line, sources in ((risk_line, risk.sources), (mvp_line, [s for f in first for s in f.sources]), (channel_line, start.sources)):
        assert sources, "the fixture items cite findings"
        assert (line.analysis, line.source_ids) == expected_sources(sources)
        assert set(line.source_ids) <= source_ids(complete, line.analysis), "the chips resolve to listed sources"
    assert (risk_line.analysis, risk_line.source_ids) == ("competitors", ["S1", "S5"])


def test_mixed_sources_keep_the_analysis_most_of_them_come_from() -> None:
    def market(source_id: str) -> StrategySourceKey:
        return StrategySourceKey(analysis="market", id=source_id)

    def competitors(source_id: str) -> StrategySourceKey:
        return StrategySourceKey(analysis="competitors", id=source_id)

    assert strategy_sources([]) == (None, [])
    assert strategy_sources([market("S2"), competitors("S1"), competitors("S4"), market("S2")]) == ("competitors", ["S1", "S4"])
    assert strategy_sources([competitors("S3"), market("S1")]) == ("competitors", ["S3"]), "a tie keeps the first named"


def test_a_short_first_release_is_listed_whole(complete: PipelineResult) -> None:
    features = [feature.model_copy(update={"tier": "later"}) if feature.rank > 2 else feature for feature in complete.mvp.features]
    result = complete.model_copy(update={"mvp": complete.mvp.model_copy(update={"features": features})})

    line = derived.strategy_summary(result)[1]
    names = [feature.name for feature in sorted(features, key=lambda feature: feature.rank)[:2]]
    assert line.text == f"First release (2 features): {names[0]} and {names[1]}."


def test_each_strategy_part_adds_its_own_line(complete: PipelineResult) -> None:
    only_swot = complete.model_copy(update={"mvp": None, "gtm": None})
    only_gtm = complete.model_copy(update={"swot": None, "mvp": None})

    assert [line.topic for line in derived.strategy_summary(only_swot)] == ["top_risk"]
    assert [line.topic for line in derived.strategy_summary(only_gtm)] == ["start_channel"]


# --- verify next (Section 12.5) ----------------------------------------------------------------


def test_verify_next_gains_the_uncertain_severe_risks_and_the_first_experiment(complete: PipelineResult) -> None:
    plain = without_strategy(complete)
    items = verify_next(complete)
    added = items[len(verify_next(plain)):]
    severe = [risk for risk in complete.swot.risks if risk.severity == "high" and risk.confidence == "low"]
    start = next(channel for channel in complete.gtm.channels if channel.start_here)

    assert items[: len(verify_next(plain))] == verify_next(plain)
    assert severe and [item.topic for item in added] == ["risk"] * len(severe) + ["channel"]
    for item, risk in zip(added, severe):
        assert risk.title in item.text and risk.early_warning_signal in item.text
        assert (item.analysis, item.source_ids) == expected_sources(risk.sources)
    assert added[-1].text == f"Run the first experiment for {start.name}: {start.first_experiment}"
    assert (added[-1].analysis, added[-1].source_ids) == expected_sources(start.sources)
    assert "constraints" not in [item.topic for item in added], "every constraint was given"


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        (None, "Confirm your team size and timeline: the MVP plan assumes a team of 2 people and 3 months to the first release."),
        (CONSTRAINTS.model_copy(update={"months_to_mvp": None}),
         "Confirm your timeline: the MVP plan assumes 3 months to the first release."),
    ],
    ids=["both_assumed", "timeline_assumed"],
)
def test_assumed_constraints_that_shape_the_mvp_are_to_be_confirmed(
    monkeypatch: pytest.MonkeyPatch, constraints, expected: str
) -> None:
    result = strategy_result(monkeypatch, constraints=constraints)

    items = [item for item in result.verify_next if item.topic == "constraints"]
    assert [item.text for item in items] == [expected]
    assert items[0].analysis is None and items[0].source_ids == []


# --- evidence strength is untouched (D-05) ----------------------------------------------------


def test_evidence_strength_is_equal_with_and_without_strategy(complete: PipelineResult) -> None:
    plain = without_strategy(complete)

    assert evidence_strength(complete) == evidence_strength(plain) == complete.evidence_strength
    assert with_derived_fields(plain).evidence_strength == complete.evidence_strength


def test_a_result_without_strategy_gets_the_same_derived_fields_as_before(complete: PipelineResult) -> None:
    labels = tuple(STRATEGY_TITLES.values())
    plain = without_strategy(complete).model_copy(
        update={"warnings": [warning for warning in complete.warnings if not warning.startswith(labels)]}
    )
    filled = with_derived_fields(plain)

    assert filled.notices == build_notices(plain.warnings, plain.errors)
    assert [line.topic for line in filled.executive_summary if line.topic in STRATEGY_TOPICS] == []


# --- notices (Sections 11.3 and 11.4) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "warning", "code", "severity", "message"),
    [
        (SWOT_LABEL, "removed 2 links to findings that are not in the digest (MKT.50, CMP.9)", "strategy_ref_removed", "info",
         "Some points were linked to findings that do not exist, so the links were removed."),
        (MVP_LABEL, "basis changed: 3 points without an existing finding now marked as assumptions", "strategy_basis_adjusted",
         "info", "3 points have no supporting finding, so they are marked as assumptions."),
        (GTM_LABEL, "removed 2 points that stated a figure no cited finding contains", "strategy_figure_removed", "warning",
         "2 points were removed because they quoted a number that no source states."),
        (SWOT_LABEL, "removed 2 points that promised an outcome (guaranteed, risk-free)", "strategy_overclaim_removed",
         "warning", "2 points were removed because they promised an outcome."),
        (MVP_LABEL, "removed 1 point that repeated an earlier point", "strategy_duplicate_removed", "info",
         "Repeated points were merged."),
        (MVP_LABEL, MVP_NO_SWOT, "strategy_inputs_missing", "warning",
         "This part was written without the risk analysis because it did not finish."),
        (GTM_LABEL, NO_MVP, "strategy_inputs_missing", "warning",
         "This part was written without the feature plan because it did not finish."),
        (MVP_LABEL, "assumed a team of 2 people and 3 months to the first release because they were not given",
         "mvp_constraints_assumed", "info",
         "Your team size and timeline were not given, so the plan assumes a team of 2 people and 3 months to the first "
         "release."),
        (MVP_LABEL, "assumed a team of 2 people because they were not given", "mvp_constraints_assumed", "info",
         "Your team size was not given, so the plan assumes a team of 2 people."),
        (MVP_LABEL, OVER_CAPACITY.format(need="4", capacity="3.6"), "mvp_over_capacity", "warning",
         "The essential features need more effort than your team and time allow. Narrow the idea or allow more time."),
        (GTM_LABEL, BUDGET_CONFLICT.format(count="1 channel", names="Radio farm shows"), "gtm_budget_conflict", "info",
         "Some channels may cost more than a bootstrapped budget."),
        (SWOT_LABEL, "skipped because it needs at least one finished analysis.", "strategy_stage_skipped", "warning",
         "This part was skipped because no analysis was available to build on."),
        (SWOT_LABEL, "cut points beyond the list limits (strengths 2, risks 1)", "strategy_items_cut", "info",
         "3 points beyond the list limits were left out."),
        (GTM_LABEL, "shortened 1 text over the length limit at a word boundary", "strategy_text_shortened", "info",
         "1 text was shortened to fit its length limit."),
        (GTM_LABEL, NO_SEGMENTS, "gtm_segments_missing", "info",
         "No customer segments were available, so the positioning is built on your stated customers and marked as an "
         "assumption."),
    ],
)
def test_each_strategy_warning_becomes_its_specified_notice(
    label: str, warning: str, code: str, severity: str, message: str
) -> None:
    notice = notice_for_warning(f"{label}: {warning}")

    assert (notice.code, notice.severity, notice.message) == (code, severity, message)
    assert notice.stage == notices.WARNING_LABELS[label] and notice.detail == f"{label}: {warning}"


def test_the_founder_part_of_a_basis_change_is_explained_too() -> None:
    notice = notice_for_warning(f"{SWOT_LABEL}: {full_repairs().warnings()[1]}")

    assert notice.code == "strategy_basis_adjusted"
    assert notice.message == (
        "1 point has no supporting finding, so it is marked as an assumption. 1 point said to come from you is not in "
        "your idea or resources, so it is marked as an AI interpretation."
    )


def test_one_notice_per_code_per_stage_adds_up_the_counts() -> None:
    warnings = [
        f"{MVP_LABEL}: removed 1 point that stated a figure no cited finding contains",
        f"{MVP_LABEL}: removed 1 link to findings that are not in the digest (MKT.50)",
        f"{GTM_LABEL}: removed 1 point that stated a figure no cited finding contains",
        f"{MVP_LABEL}: removed 2 points that stated a figure no cited finding contains",
        f"{MVP_LABEL}: removed 2 links to risks that are not in the risk analysis (RSK.9, R3)",
        f"{MVP_LABEL}: {RATINGS_CLAMPED.format(count='2 ratings')}",
        f"{MVP_LABEL}: {TARGETS_REMOVED.format(count='1 metric')}",
    ]

    built = build_notices(warnings, [])

    assert [(notice.stage, notice.code) for notice in built] == [
        (STAGE_MVP, "strategy_figure_removed"),
        (STAGE_MVP, "strategy_ref_removed"),
        (STAGE_GTM, "strategy_figure_removed"),
        (STAGE_MVP, "quality_adjusted"),
    ]
    assert built[0].message == "3 points were removed because they quoted a number that no source states."
    assert built[0].detail == "\n".join([warnings[0], warnings[3]])
    assert built[1].detail == "\n".join([warnings[1], warnings[4]])
    assert built[2].message == "1 point was removed because it quoted a number that no source states."
    assert built[3].message == "A quality check adjusted part of the MVP plan. Open the details to see what changed."
    assert built[3].detail == "\n".join(warnings[5:])


def test_milestone_2_warnings_still_get_one_notice_each() -> None:
    warnings = ["Market opportunity: segments[0]: it is not about the problem this idea solves, so it was removed"] * 2

    assert len(build_notices(warnings, [])) == 2


@pytest.mark.parametrize("label", [SWOT_LABEL, MVP_LABEL, GTM_LABEL])
def test_no_strategy_notice_shows_a_field_path_an_id_or_a_code(label: str) -> None:
    for warning in agent_warnings():
        notice = notice_for_warning(f"{label}: {warning}")
        assert not leaks(notice.message), notice.message
        assert not any(marker in notice.message for marker in TECHNICAL), notice.message
        assert (notice.message[0].isupper() or notice.message[0].isdigit()) and notice.message.endswith("."), notice.message
    for notice in build_notices([f"{label}: {warning}" for warning in agent_warnings()], []):
        assert not leaks(notice.message) and not any(marker in notice.message for marker in TECHNICAL), notice.message


@pytest.mark.parametrize(
    ("label", "area"),
    [(SWOT_LABEL, "the strengths and risks"), (MVP_LABEL, "the MVP plan"), (GTM_LABEL, "the go-to-market plan")],
)
def test_an_unknown_strategy_warning_gets_the_general_message(label: str, area: str) -> None:
    for warning in ("some future check changed positioning.for_whom[0] and S4", RATINGS_CLAMPED.format(count="2 ratings"),
                    PHASES_MISSING.format(count=2, total=3, names="Launch")):
        notice = notice_for_warning(f"{label}: {warning}")
        assert notice.code == notices.CODE_FALLBACK and notice.severity == "info"
        assert notice.message == f"A quality check adjusted part of {area}. Open the details to see what changed."
        assert notice.detail == f"{label}: {warning}"


def test_the_strategy_rules_apply_only_under_a_strategy_label() -> None:
    for warning in full_repairs().warnings():
        assert notice_for_warning(warning).code == notices.CODE_FALLBACK
        assert notice_for_warning(f"Market opportunity: {warning}").code == notices.CODE_FALLBACK


def test_a_strategy_stage_error_or_skip_names_the_stage() -> None:
    error = StageError(stage=STAGE_MVP, code="llm_api_error", message="The AI service is busy right now.")

    assert notice_for_error(error).message == "Recommending MVP features did not finish. The AI service is busy right now."
    assert notice_for_warning(SKIP_NO_TIME.format(label=GTM_LABEL)).message == (
        "Planning go-to-market was skipped because the run reached its time limit."
    )
    cancelled = notice_for_warning(SKIP_CANCELLED.format(label=SWOT_LABEL))
    assert (cancelled.code, cancelled.message) == (
        "run_cancelled", "Assessing strengths and risks was skipped because the run was cancelled."
    )
    skipped = notice_for_warning(SKIP_NO_ANALYSIS.format(label=MVP_LABEL))
    assert (skipped.stage, skipped.code) == (STAGE_MVP, "strategy_stage_skipped")


def test_a_clean_seven_stage_run_has_no_strategy_notice(complete: PipelineResult) -> None:
    assert not [notice for notice in complete.notices if notice.stage in STRATEGY_TITLES]
    assert len(complete.notices) == len(complete.warnings) + len(complete.errors)


def test_inputs_a_stage_was_written_without_come_from_its_quality_block(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, pipeline={"market_llm": (LLMAPIError(),)})

    assert result.market is None and result.swot and result.mvp and result.gtm
    missing = {notice.stage: notice for notice in result.notices if notice.code == "strategy_inputs_missing"}
    assert set(missing) == {STAGE_SWOT, STAGE_MVP, STAGE_GTM}
    for notice in missing.values():
        assert notice.message == "This part was written without the market analysis because it did not finish."
        assert notice.severity == "warning" and notice.detail == "inputs missing: market"


def test_a_missing_risk_analysis_is_one_notice_that_keeps_the_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, swot=LLMAPIError())

    assert result.swot is None and result.mvp and result.gtm
    for stage, label, warning in ((STAGE_MVP, MVP_LABEL, MVP_NO_SWOT), (STAGE_GTM, GTM_LABEL, GTM_NO_SWOT)):
        found = [notice for notice in result.notices if notice.stage == stage and notice.code == "strategy_inputs_missing"]
        assert len(found) == 1, stage
        assert found[0].message == "This part was written without the risk analysis because it did not finish."
        assert found[0].detail.split("\n") == [f"{label}: {warning}", "inputs missing: swot"]
    assert [notice.stage for notice in result.notices if notice.severity == "error"] == [STAGE_SWOT]
    assert any(notice.message.startswith("Assessing strengths and risks did not finish.") for notice in result.notices)


def test_two_missing_inputs_are_named_in_one_notice() -> None:
    built = build_notices([f"{GTM_LABEL}: {NO_MVP}"], [], {STAGE_GTM: ["competitors", "swot", "mvp"]})

    assert len(built) == 1
    assert built[0].message == (
        "This part was written without the competitor analysis, the risk analysis and the feature plan because they "
        "did not finish."
    )


def test_assumed_resources_become_a_notice_on_the_mvp_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    result = strategy_result(monkeypatch, constraints=None)

    found = [notice for notice in result.notices if notice.code == "mvp_constraints_assumed"]
    assert [(notice.stage, notice.message) for notice in found] == [(
        STAGE_MVP,
        "Your team size and timeline were not given, so the plan assumes a team of 2 people and 3 months to the first "
        "release.",
    )]
