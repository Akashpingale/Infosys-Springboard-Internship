"""The downloadable Markdown report (`frontend/analysis_views.report_markdown`).

Two shapes matter: a Milestone 1-only result, where the export must stay exactly the research
report it has always been, and a full Milestone 1 + Milestone 2 result, where it must carry the
idea, the research, the market analysis and the competitor analysis. Everything is built from
real pipeline results produced with fakes, so no claim in the document is invented by the test.
"""

import pytest

import orchestrator
from agents.web_search_agent import render_markdown
from frontend import analysis_views as views
from models.schemas import PipelineResult, StageError
from tests.domain_fakes import DOMAIN_IDS, DOMAINS, Domain
from tests.pipeline_fakes import use_full_pipeline

SECRETS = ("test-llm-key", "test-tavily-key")


def full_result(monkeypatch: pytest.MonkeyPatch, domain: Domain) -> PipelineResult:
    use_full_pipeline(
        monkeypatch,
        extraction=(domain.extraction_reply,),
        search=(domain.search,),
        market_search=(domain.market_search,),
        market_llm=(domain.market_reply,),
        competitor_search=(domain.competitor_search,),
        competitor_llm=(domain.candidate_reply, domain.analysis_reply),
    )
    result = orchestrator.run_pipeline(domain.submission, orchestrator.FULL_STAGES)
    assert result.market is not None and result.competitors is not None, "the fixture must be complete"
    return result


@pytest.fixture
def fintech(monkeypatch: pytest.MonkeyPatch) -> PipelineResult:
    return full_result(monkeypatch, DOMAINS[1])


def headings(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("#")]


# --- Milestone 1 only: the export is unchanged ------------------------------------------------


def test_without_an_analysis_the_export_is_exactly_the_research_report(fintech: PipelineResult) -> None:
    milestone_1 = fintech.model_copy(update={"market": None, "competitors": None})

    assert views.report_markdown(milestone_1) == render_markdown(milestone_1.search)
    assert views.report_file_name(milestone_1) == views.RESEARCH_FILE_NAME == "market_research.md"
    assert not views.has_analysis(milestone_1)


def test_without_a_search_or_an_analysis_there_is_nothing_to_download() -> None:
    failed = PipelineResult(
        status="failed",
        errors=[StageError(stage="extraction", code="llm_not_configured", message="The AI service is not configured.")],
    )
    assert views.report_markdown(failed) == "", "the UI offers no button for an empty report"


def test_the_research_report_keeps_its_own_heading_when_alone(fintech: PipelineResult) -> None:
    milestone_1 = fintech.model_copy(update={"market": None, "competitors": None})
    assert views.report_markdown(milestone_1).startswith("# Market and competitor research")


# --- Milestone 1 + Milestone 2: the full report ------------------------------------------------


@pytest.mark.parametrize("domain", DOMAINS, ids=DOMAIN_IDS)
def test_the_full_report_covers_both_milestones_for_every_domain(
    monkeypatch: pytest.MonkeyPatch, domain: Domain
) -> None:
    result = full_result(monkeypatch, domain)
    text = views.report_markdown(result)

    assert text.startswith(f"# {views.REPORT_TITLE}")
    for heading in (
        "## What the system understood",
        "## Market and competitor research",
        "## Market opportunity",
        "## Competitors",
    ):
        assert heading in headings(text), heading
    assert views.report_file_name(result) == views.REPORT_FILE_NAME == "validation_report.md"


def test_the_report_carries_the_status_and_timings(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)

    assert "Status: Complete" in text
    assert "market opportunity" in text and "competitor analysis" in text, "readable stage names"


def test_the_report_lists_warnings_and_errors_with_their_stage(fintech: PipelineResult) -> None:
    degraded = fintech.model_copy(update={
        "status": "partial",
        "warnings": ["Competitor analysis: a targeted search found no results"],
        "errors": [StageError(stage="market_opportunity", code="llm_api_error", message="The AI service is busy.")],
    })
    text = views.report_markdown(degraded)

    assert "Status: Partial" in text
    assert "- Competitor analysis: a targeted search found no results" in text
    assert "- market opportunity: The AI service is busy. (llm_api_error)" in text


def test_the_extracted_idea_is_written_out(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    idea = fintech.idea

    assert f"**{idea.idea_title}**" in text
    assert f"- Industry: {idea.industry}" in text
    assert idea.problem in text and idea.solution in text
    for feature in idea.key_features:
        assert feature in text


def test_the_research_section_nests_under_the_report_title(fintech: PipelineResult) -> None:
    """The reused renderer's headings are pushed one level down, so the document has one H1."""
    text = views.report_markdown(fintech)
    found = headings(text)

    assert found.count(f"# {views.REPORT_TITLE}") == 1
    assert len([line for line in found if line.startswith("# ")]) == 1, "exactly one top-level heading"
    assert "## Market and competitor research" in found
    assert "### Market size and trends" in found, "the search sections nest too"
    for section in fintech.search.sections:
        assert f"### {section.label}" in found


def test_the_market_section_covers_every_part_of_the_analysis(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    market = fintech.market

    for heading in ("### Industry overview", "### Customer demand", "### Market size",
                    "### Trends", "### Customer segments", "### Opportunities and limitations"):
        assert heading in headings(text), heading
    assert f"- Market category: {market.industry_overview.market_category}" in text
    assert market.market_demand.summary in text
    for segment in market.segments:
        assert views.segment_heading(segment) in text
    assert f"**Priority segment: {market.priority_segment.segment_name}**" in text
    assert market.priority_segment.rationale in text
    for caveat in market.caveats:
        assert caveat in text


def test_the_market_size_table_shows_every_figure_with_its_status(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)

    assert "| Figure | Value | Status | Sources | Note |" in text
    for row in views.market_size_rows(fintech.market):
        assert f"| {row['Figure']} | {row['Value']} | {row['Status']} |" in text
    assert views.MSG_BROADER_MARKETS in text, "the broader-market figures are labelled as context"
    for row in views.broader_market_rows(fintech.market):
        assert row["Value"] in text


def test_the_competitor_section_groups_and_compares_them(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    analysis = fintech.competitors

    for heading, group in views.competitor_groups(analysis):
        assert f"### {heading} ({len(group)})" in headings(text)
    for competitor in analysis.competitors:
        assert f"**{competitor.name}**" in text
    assert "### Feature comparison" in headings(text)
    assert "| Competitor | " in text
    for feature in analysis.comparison.features:
        assert feature in text
    assert "| Feature | Competitors with evidence |" in text


def test_the_gaps_carry_their_caveat(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    assert fintech.competitors.market_gaps, "the fixture has a gap to show"

    for gap in fintech.competitors.market_gaps:
        assert views.gap_line(gap) in text
        assert f"  - {gap.caveat}" in text


def test_the_searches_run_for_the_analysis_are_listed(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    queries = fintech.competitors.queries_used

    assert queries, "the fixture ran targeted searches"
    assert f"### Searches run for this analysis ({len(queries)})" in headings(text)
    for query in queries:
        assert query in text


def test_every_source_appears_as_a_markdown_link(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)

    for sources in (fintech.market.sources, fintech.competitors.sources):
        assert sources
        for line in views.source_lines(sources):
            assert line in text
        for source in sources:
            assert f"({source.url})" in text


def test_each_claim_shows_its_basis_in_words(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)

    assert "(Sourced:" in text, "sourced claims name the ids they rest on"
    assert "(AI interpretation" in text or "(Assumption" in text
    assert "Basis: User provided" in text, "the founder-named competitor is labelled"


def test_the_evidence_level_and_notes_are_stated_for_both_analyses(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)

    assert text.count(views.quality_text(fintech.market.data_quality)) >= 1
    for note in fintech.market.data_quality.notes:
        assert note in text
    for note in fintech.competitors.data_quality.notes:
        assert note in text


# --- partial results: nothing is invented -----------------------------------------------------


def test_a_missing_market_analysis_says_so_and_keeps_the_competitors(fintech: PipelineResult) -> None:
    partial = fintech.model_copy(update={"status": "partial", "market": None})
    text = views.report_markdown(partial)

    assert views.MSG_NO_MARKET in text
    assert "## Competitors" in headings(text)
    assert "### Feature comparison" in headings(text)
    assert views.report_file_name(partial) == views.REPORT_FILE_NAME


def test_a_missing_competitor_analysis_says_so_and_keeps_the_market(fintech: PipelineResult) -> None:
    partial = fintech.model_copy(update={"status": "partial", "competitors": None})
    text = views.report_markdown(partial)

    assert views.MSG_NO_COMPETITORS in text
    assert "## Market opportunity" in headings(text)
    assert "### Market size" in headings(text)


def test_a_missing_search_bundle_is_stated_rather_than_left_blank(fintech: PipelineResult) -> None:
    without_search = fintech.model_copy(update={"search": None})
    text = views.report_markdown(without_search)

    assert views.MSG_NO_RESEARCH in text
    assert "## Market and competitor research" in headings(text)


def test_no_key_or_traceback_can_reach_the_report(fintech: PipelineResult) -> None:
    text = views.report_markdown(fintech)
    assert all(secret not in text for secret in SECRETS)
    assert "Traceback" not in text


# --- table safety -----------------------------------------------------------------------------


def test_a_pipe_in_a_value_cannot_break_a_table_column() -> None:
    rows = [{"Figure": "TAM", "Value": "USD 1 | 2 billion", "Note": "a\nb"}]
    rendered = views._table(rows)

    assert rendered[0] == "| Figure | Value | Note |"
    assert rendered[2] == "| TAM | USD 1 \\| 2 billion | a b |", "pipes escaped, newlines flattened"


def test_an_empty_table_renders_nothing() -> None:
    assert views._table([]) == []
