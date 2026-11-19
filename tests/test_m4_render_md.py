import re

import pytest

from agents.report_checks import with_consistency
from models.report import (
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    FactPair,
    FactsBlock,
    ParagraphBlock,
    ReportDocument,
    ReportItem,
    SubheadingBlock,
    TableBlock,
)
from tests.m4_report_fixtures_synthetic import ROOT, SYNTHETIC_RESULTS, full_document, synthetic_complete
from tests.test_m4_report_agent import report_of, use_writer
from utils.report_render_md import escape_inline, escape_md, render_report_md, safe_url

GOLDEN = ROOT / "tests" / "snapshots" / "m4_report_synthetic.md"
FAKE_KEY = "tvly-" + "PLANTEDFAKE" + "0123456789"
HOSTILE = '<script>alert("x")</script> & <b>bold</b> | pipe `tick` **star** _under_ ~strike~ $5 \\ back [link](javascript:alert(1))'
LEADERS = ("# Heading injection", "1. Numbered injection", "- Dash injection", "+ Plus injection", "> Quote injection",
           "=== Setext injection")


def hostile_document() -> ReportDocument:
    document = full_document(synthetic_complete())
    summary = next(section for section in document.sections if section.id == "executive_summary")
    summary.blocks = [
        ParagraphBlock(text=HOSTILE, basis="ai_interpretation", cites=[1]),
        *(ParagraphBlock(text=leader) for leader in LEADERS),
        BulletsBlock(items=[ReportItem(text=HOSTILE, basis="sourced", cites=[1]),
                            *(ReportItem(text=leader) for leader in LEADERS)]),
        TableBlock(caption=HOSTILE, columns=["A | B", "`C`"], rows=[[HOSTILE, "x|y"], ["1. one", "# two"]],
                   col_align=["left", "right"], row_cites=[[1], []]),
        CalloutBlock(kind="warning", text=HOSTILE),
        FactsBlock(pairs=[FactPair(label=HOSTILE, value=HOSTILE)]),
        SubheadingBlock(text=HOSTILE + " #"),
    ]
    document.bibliography[0].title = HOSTILE
    document.bibliography[0].domain = "<i>evil</i>.example"
    return document


def unescaped(line: str, character: str) -> int:
    return len(re.findall(r"(?<!\\)" + re.escape(character), line))


@pytest.fixture(scope="module")
def synthetic_md() -> str:
    with pytest.MonkeyPatch.context() as monkeypatch:
        use_writer(monkeypatch)
        return render_report_md(report_of(synthetic_complete()))


def test_the_synthetic_report_matches_the_golden_markdown(synthetic_md: str) -> None:
    assert synthetic_md == GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_the_markdown_has_headings_by_level_in_catalogue_order(synthetic_md: str) -> None:
    lines = synthetic_md.splitlines()
    assert lines[0] == "# Startup validation report"
    assert [line for line in lines if line.startswith("# ")] == [lines[0]]
    sections = [line[3:] for line in lines if line.startswith("## ")]
    assert sections == ["Executive summary", "Validation at a glance", "The idea as understood", "Market opportunity",
                        "Competitive landscape", "SWOT", "Risk assessment", "MVP recommendation", "Go-to-market strategy",
                        "Recommended next steps", "How this report was produced", "Limitations", "Sources",
                        "Appendix A: Run details", "Appendix B: Terms"]
    assert "### Key insights" in lines and "### What to verify" in lines


def test_citations_basis_labels_callouts_and_the_bibliography(synthetic_md: str) -> None:
    lines = synthetic_md.splitlines()
    assert "- Market size (TAM): USD 1.8 billion (AI crop disease detection market, 2025). [Sourced] [2]" in lines
    assert "> **Note:** AI-assisted analysis; interpretations are labelled." in lines
    assert "> **Caveat:** This report interprets the evidence found for this idea and does not predict results." in lines
    assert "2. Crop AI market report (reports.example) <https://reports.example/crop-ai-market> Cited in: Executive summary, " \
           "Market opportunity." in lines
    numbered = [line for line in lines if re.match(r"^\d+\. ", line)]
    assert [int(line.split(".", 1)[0]) for line in numbered] == list(range(1, len(numbered) + 1))


def test_tables_are_github_tables_with_alignment_and_a_sources_column(synthetic_md: str) -> None:
    lines = synthetic_md.splitlines()
    start = lines.index("**Feature coverage**")
    assert lines[start + 2:start + 4] == ["| Feature | Competitors with evidence |", "| --- | ---: |"]
    header = lines.index("**Market size for this idea**") + 2
    assert lines[header] == "| Figure | Value | Status | Note | Sources |"
    assert lines[header + 2] == "| TAM | USD 1.8 billion | Sourced | AI crop disease detection market, 2025 | [2] |"
    assert "| Plantix | + Evidence found | ? Unclear | + Evidence found | + Evidence found | \u2013 No evidence found in the " \
           "sources | ? Unclear | [3] [4] |" in lines


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_every_synthetic_fixture_renders_with_every_section(name: str) -> None:
    document = full_document(SYNTHETIC_RESULTS[name]())
    text = render_report_md(document)
    for section in [*document.sections, *document.appendix_sections]:
        if section.id != "cover":
            assert f"## {section.title}" in text.splitlines()
    for missing in document.meta.sections_missing:
        assert f"> **Note:** Not included: {escape_inline(missing.reason)}" in text.splitlines()
    assert render_report_md(document) == text


def test_hostile_text_in_every_block_type_is_escaped() -> None:
    text = render_report_md(hostile_document())
    for marker in ("<script", "</script", "<b>", "<i>"):
        assert marker not in text
    assert "&lt;script&gt;" in text and "&lt;b&gt;bold&lt;/b&gt;" in text and "&lt;i&gt;evil&lt;/i&gt;" in text
    assert not re.search(r"(?<!\\)\]\(javascript:", text)
    assert "\\[link\\](javascript:alert(1))" in text
    for line in text.splitlines():
        assert unescaped(line, "`") == 0
        assert unescaped(line, "~") == 0
        assert unescaped(line, "$") == 0
        assert "**star**" not in line


def test_hostile_text_cannot_break_a_table_row() -> None:
    lines = render_report_md(hostile_document()).splitlines()
    caption = next(index for index, line in enumerate(lines) if line.startswith("**&lt;script"))
    table = lines[caption + 2:caption + 6]
    assert all(line.startswith("| ") and line.endswith(" |") for line in table)
    assert [unescaped(line, "|") for line in table] == [4, 4, 4, 4]
    assert table[1] == "| --- | ---: | --- |"
    assert table[3] == "| 1. one | \\# two |   |"


def test_leading_markers_cannot_start_headings_lists_or_quotes() -> None:
    lines = render_report_md(hostile_document()).splitlines()
    for expected in ("\\# Heading injection", "1\\. Numbered injection", "\\- Dash injection", "\\+ Plus injection",
                     "&gt; Quote injection", "\\=== Setext injection"):
        assert expected in lines
        assert f"- {expected}" in lines
    assert not any(line.startswith(("# Heading", "1. Numbered", "- Dash injection", "> Quote")) for line in lines)
    assert any(line.startswith("### ") and line.endswith(" \\#") for line in lines)


def test_links_are_emitted_only_for_http_and_https_addresses() -> None:
    document = hostile_document()
    document.bibliography[1] = BibEntry.model_construct(**{**document.bibliography[1].model_dump(),
                                                           "url": "javascript:alert(1)"})
    document.bibliography[2] = BibEntry.model_construct(**{**document.bibliography[2].model_dump(),
                                                           "url": "https://example.org/a b<c>"})
    lines = render_report_md(document).splitlines()
    second = next(line for line in lines if line.startswith("2. "))
    third = next(line for line in lines if line.startswith("3. "))
    assert "<javascript:" not in second and "javascript:alert(1)" in second
    assert "<https://example.org/a" not in third and "https://example.org/a b&lt;c&gt;" in third
    assert "<https://plantix.example/pricing>" in "\n".join(lines)


@pytest.mark.parametrize(("url", "expected"), [
    ("https://example.org/page?a=1&b=2", "https://example.org/page?a=1&b=2"),
    ("HTTP://EXAMPLE.ORG", "HTTP://EXAMPLE.ORG"),
    ("javascript:alert(1)", None),
    ("data:text/html,x", None),
    ("ftp://example.org", None),
    ("https://example.org/a b", None),
    ("https://example.org/<x>", None),
    ('https://example.org/"x"', None),
    ("", None),
    (None, None),
])
def test_the_url_allowlist(url: str | None, expected: str | None) -> None:
    assert safe_url(url) == expected


def test_control_characters_and_line_breaks_cannot_split_a_line() -> None:
    assert escape_md("one\ntwo\r\n# three\x00four\x1b") == "one two \\# three four"
    assert escape_inline("  spaced\tout  ") == "spaced out"


def test_a_planted_key_is_reported_by_the_consistency_checks_and_never_breaks_the_markdown() -> None:
    document = hostile_document()
    document.sections[2].blocks.append(ParagraphBlock(text=f"key {FAKE_KEY}"))
    checked = with_consistency(document, synthetic_complete())
    assert next(check for check in checked.meta.consistency.checks if check.id == "C-11").passed is False
    assert render_report_md(checked).endswith("\n")


def test_an_empty_bibliography_says_why_sources_are_not_included() -> None:
    document = full_document(SYNTHETIC_RESULTS["minimal"]())
    assert document.bibliography == []
    lines = render_report_md(document).splitlines()
    sources = lines.index("## Sources")
    assert lines[sources + 2] == "> **Note:** Not included: No sources were cited in this report."
    assert not any(re.match(r"^\d+\. ", line) for line in lines)


def test_the_golden_file_holds_no_key_shaped_text() -> None:
    from agents.strategy_checks import secret_findings

    assert secret_findings(GOLDEN.read_text(encoding="utf-8")) == []
