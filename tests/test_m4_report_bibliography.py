import pytest

from agents.report_bibliography import (
    CAP_NOTE,
    REASON_NO_SOURCES,
    SUMMARY_TITLE,
    number_citations,
    source_pages,
)
from agents.report_sections import NOT_INCLUDED, source_key
from models.report import BulletsBlock, CalloutBlock, ParagraphBlock, ReportDocument, TableBlock
from models.schemas import LabeledItem, PipelineResult, SourceRef
from tests.m4_report_fixtures_synthetic import draft, synthetic_complete, synthetic_minimal, synthetic_partial


def numbered(result: PipelineResult, **options) -> ReportDocument:
    return number_citations(draft(result), result, **options)


def cites_in_order(document: ReportDocument) -> list[tuple[str, int]]:
    found = []
    for section in [*document.sections, *document.appendix_sections]:
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                found += [(section.id, number) for number in block.cites]
            elif isinstance(block, BulletsBlock):
                found += [(section.id, number) for entry in block.items for number in entry.cites]
            elif isinstance(block, TableBlock):
                found += [(section.id, number) for row in block.row_cites for number in row]
    return found


def entry_for(document: ReportDocument, url: str):
    return next(entry for entry in document.bibliography if entry.url == url)


def with_market(result: PipelineResult, **changes) -> PipelineResult:
    return result.model_copy(update={"market": result.market.model_copy(update=changes)})


def test_sources_are_numbered_in_order_of_first_citation() -> None:
    document = numbered(synthetic_complete())
    first_seen = list(dict.fromkeys(number for _, number in cites_in_order(document)))
    assert first_seen == list(range(1, len(document.bibliography) + 1))
    assert [entry.number for entry in document.bibliography] == first_seen


def test_the_same_page_cited_by_both_analyses_gets_one_number() -> None:
    document = numbered(synthetic_complete())
    plantix = entry_for(document, "https://plantix.example/about")
    assert plantix.analyses == ["market", "competitors"]
    assert sum(1 for entry in document.bibliography if entry.url == "https://plantix.example/about") == 1
    assert len(document.bibliography) == 8


def test_the_same_id_in_two_analyses_can_be_two_pages() -> None:
    document = numbered(synthetic_complete())
    market_s1 = entry_for(document, "https://reports.example/crop-ai-market")
    assert market_s1.number != entry_for(document, "https://plantix.example/about").number
    assert market_s1.analyses == ["market"] and market_s1.domain == "reports.example"


def test_a_url_differing_only_by_www_or_a_trailing_slash_is_one_page() -> None:
    complete = synthetic_complete()
    sources = [*complete.market.sources]
    sources[1] = SourceRef(id=sources[1].id, title=sources[1].title, url="https://www.plantix.example/about/")
    document = numbered(with_market(complete, sources=sources))
    assert sum(1 for entry in document.bibliography if entry.domain == "plantix.example" and "about" in entry.url) == 1


def test_the_search_engine_summary_is_one_entry_without_a_page() -> None:
    complete = synthetic_complete()
    summary = SourceRef(id="S0", title="Search engine summary", url="")
    limitation = LabeledItem(text="A summary-only remark.", basis="ai_interpretation", source_ids=["S0"])
    competitors = complete.competitors.model_copy(update={
        "sources": [*complete.competitors.sources, summary],
        "differentiation_opportunities": [*complete.competitors.differentiation_opportunities,
                                          LabeledItem(text="Another summary remark.", basis="ai_interpretation", source_ids=["S0"])],
    })
    result = with_market(complete, sources=[*complete.market.sources, summary],
                         limitations=[*complete.market.limitations, limitation]).model_copy(update={"competitors": competitors})
    document = numbered(result)
    entries = [entry for entry in document.bibliography if not entry.has_page]
    assert len(entries) == 1
    assert entries[0].title == SUMMARY_TITLE and entries[0].url is None and entries[0].domain == ""
    assert entries[0].analyses == ["market", "competitors"]


def test_an_uncited_source_is_left_out() -> None:
    complete = synthetic_complete()
    extra = SourceRef(id="S9", title="Never cited", url="https://uncited.example/page")
    document = numbered(with_market(complete, sources=[*complete.market.sources, extra]))
    assert all(entry.url != "https://uncited.example/page" for entry in document.bibliography)


def test_a_citation_of_a_missing_source_is_dropped() -> None:
    complete = synthetic_complete()
    ghost = LabeledItem(text="A claim citing a deleted source.", basis="sourced", source_ids=["S42"])
    document = numbered(with_market(complete, opportunities=[*complete.market.opportunities, ghost]))
    found = next(entry for block in document.sections[4].blocks if isinstance(block, BulletsBlock)
                 for entry in block.items if entry.text == ghost.text)
    assert found.cites == []


def test_strategy_citations_of_a_removed_analysis_are_dropped() -> None:
    document = numbered(synthetic_partial())
    assert all(entry.analyses == ["competitors"] for entry in document.bibliography)
    numbers = {entry.number for entry in document.bibliography}
    assert {number for _, number in cites_in_order(document)} == numbers


def test_a_javascript_link_is_kept_as_text_without_a_link() -> None:
    complete = synthetic_complete()
    sources = [*complete.market.sources]
    sources[0] = SourceRef(id=sources[0].id, title="Hostile page", url="javascript:alert(1)")
    document = numbered(with_market(complete, sources=sources))
    hostile = next(entry for entry in document.bibliography if entry.title == "Hostile page")
    assert hostile.url is None and hostile.has_page and hostile.domain == ""


def test_each_entry_lists_the_sections_that_cite_it() -> None:
    document = numbered(synthetic_complete())
    for entry in document.bibliography:
        assert entry.cited_in == list(dict.fromkeys(section for section, number in cites_in_order(document) if number == entry.number))


def test_the_internal_keys_are_replaced_by_numbers() -> None:
    document = numbered(synthetic_complete())
    for section in [*document.sections, *document.appendix_sections]:
        for block in section.blocks:
            assert not getattr(block, "keys", []) and not getattr(block, "row_keys", [])
            for entry in getattr(block, "items", []):
                assert not entry.keys
    assert cites_in_order(document)


def test_the_cap_limits_the_list_and_says_so() -> None:
    document = numbered(synthetic_complete(), cap=2)
    assert [entry.number for entry in document.bibliography] == [1, 2]
    assert {number for _, number in cites_in_order(document)} == {1, 2}
    sources = next(section for section in document.sections if section.id == "sources")
    assert sources.blocks == [CalloutBlock(kind="note", text=CAP_NOTE.format(cap=2))]


def test_a_report_without_sources_lists_the_sources_section_as_missing() -> None:
    document = numbered(synthetic_minimal())
    assert document.bibliography == []
    assert "sources" not in document.meta.sections_included
    assert {entry.id: entry.reason for entry in document.meta.sections_missing}["sources"] == REASON_NO_SOURCES
    ids = [entry.id for entry in document.meta.sections_missing]
    assert ids == sorted(ids, key=[*(s.id for s in document.sections), *(s.id for s in document.appendix_sections)].index)
    sources = next(section for section in document.sections if section.id == "sources")
    assert sources.blocks == [CalloutBlock(kind="note", text=NOT_INCLUDED.format(reason=REASON_NO_SOURCES))]


def test_numbering_leaves_the_draft_unchanged() -> None:
    result = synthetic_complete()
    first = draft(result)
    before = first.model_dump(mode="json")
    number_citations(first, result)
    assert first.model_dump(mode="json") == before


@pytest.mark.parametrize(("analysis", "source_id", "expected"), [("market", " s1 ", "market:S1"), ("competitors", "S2", "competitors:S2")])
def test_source_keys_follow_the_interface(analysis: str, source_id: str, expected: str) -> None:
    assert source_key(analysis, source_id) == expected


def test_every_source_of_the_result_has_a_page_record() -> None:
    result = synthetic_complete()
    pages = source_pages(result)
    assert set(pages) == {source_key("market", s.id) for s in result.market.sources} | {
        source_key("competitors", s.id) for s in result.competitors.sources
    }
