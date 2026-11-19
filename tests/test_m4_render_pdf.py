import re
import shutil
from io import BytesIO
from pathlib import Path

import pytest
import reportlab
from pypdf import PdfReader

from agents.report_checks import with_consistency
from config import get_settings
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
from models.schemas import PipelineResult
from routes.meta_routes import APP_NAME
from tests.m4_report_fixtures_synthetic import ROOT, SYNTHETIC_RESULTS, full_document, synthetic_complete
from tests.test_m4_report_agent import LIVE, SAVED, load, report_of, use_writer
from utils.errors import ReportRenderError, ReportTooLargeError
from utils.report_render_md import render_report_md
from utils.report_render_pdf import (
    FONT_FILES,
    PAGE_CAP,
    missing_font_files,
    render_report_pdf,
)

BUNDLED = (("Vera.ttf", "IBMPlexSans-Regular.ttf"), ("VeraBd.ttf", "IBMPlexSans-Bold.ttf"),
           ("VeraIt.ttf", "IBMPlexSans-Italic.ttf"), ("Vera.ttf", "IBMPlexMono-Regular.ttf"))
FONT_NAMES = [name for _, name in FONT_FILES]
FAKE_KEY = "tvly-" + "PLANTEDFAKE" + "0123456789"
HOSTILE = '<script>alert("x")</script> & <b>bold</b> <font size=40>big</font> &amp; | `tick` javascript:alert(1)'
CHARACTERS = "Prices \u20ac 12, \u00a3 9, \u00a5 800 and $ 5. Caf\u00e9, se\u00f1or, \u00fcber, \u00f6l, gar\u00e7on \u2013 \u201cquoted\u201d \u00d7 2"


def bundled_fonts(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    source = Path(reportlab.__file__).parent / "fonts"
    for original, target in BUNDLED:
        shutil.copyfile(source / original, folder / target)
    return folder


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def pages_text(pdf: bytes) -> list[str]:
    return [page.extract_text() for page in PdfReader(BytesIO(pdf)).pages]


def links(pdf: bytes) -> tuple[list[str], list[int]]:
    reader = PdfReader(BytesIO(pdf))
    numbers = {page.indirect_reference.idnum: index for index, page in enumerate(reader.pages, start=1)}
    uris, targets = [], []
    for page in reader.pages:
        for annotation in page.get("/Annots") or []:
            link = annotation.get_object()
            action = link.get("/A")
            if action is not None:
                uris.append(str(action.get_object().get("/URI")))
            else:
                targets.append(numbers[link["/Dest"][0].idnum])
    return uris, targets


@pytest.fixture(scope="module")
def fonts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return bundled_fonts(tmp_path_factory.mktemp("report-fonts"))


@pytest.fixture(scope="module")
def synthetic() -> ReportDocument:
    with pytest.MonkeyPatch.context() as monkeypatch:
        use_writer(monkeypatch)
        return report_of(synthetic_complete())


@pytest.fixture(scope="module")
def synthetic_pdf(synthetic: ReportDocument, fonts: Path) -> bytes:
    return render_report_pdf(synthetic, font_dir=fonts)


def hostile_document() -> ReportDocument:
    document = full_document(synthetic_complete())
    summary = next(section for section in document.sections if section.id == "executive_summary")
    summary.blocks = [
        ParagraphBlock(text=HOSTILE, basis="ai_interpretation", cites=[1]),
        BulletsBlock(items=[ReportItem(text=HOSTILE, basis="sourced", cites=[1])]),
        TableBlock(caption=HOSTILE, columns=[HOSTILE, "<b>"], rows=[[HOSTILE, "</para>"]], col_align=["left", "right"],
                   row_cites=[[1]]),
        CalloutBlock(kind="warning", text=HOSTILE),
        FactsBlock(pairs=[FactPair(label=HOSTILE, value="<br/>")]),
        SubheadingBlock(text=HOSTILE),
    ]
    document.bibliography[0].title = HOSTILE
    document.bibliography[0].domain = "<i>evil</i>"
    document.meta.idea_title = HOSTILE
    return document


def test_the_pdf_opens_and_has_every_section_in_order(synthetic: ReportDocument, synthetic_pdf: bytes) -> None:
    reader = PdfReader(BytesIO(synthetic_pdf))
    assert 2 < len(reader.pages) <= PAGE_CAP
    titles = [section.title for section in [*synthetic.sections, *synthetic.appendix_sections] if section.id != "cover"]
    assert [item.title for item in reader.outline] == titles
    first = squeeze(reader.pages[0].extract_text())
    assert squeeze("Startup validation report") in first and squeeze("CropScan: AI crop disease detection") in first


def test_the_table_of_contents_lists_the_right_page_numbers(synthetic: ReportDocument, synthetic_pdf: bytes) -> None:
    reader = PdfReader(BytesIO(synthetic_pdf))
    texts = pages_text(synthetic_pdf)
    outline = [(item.title, reader.get_destination_page_number(item) + 1) for item in reader.outline]
    for title, page in outline:
        assert title in [line.strip() for line in texts[page - 1].splitlines()], (title, page)
    contents = texts[0].split("Contents", 1)[1]
    printed = [int(number) for number in re.findall(r"(?:\.\s+)+(\d+)\s*$", contents, flags=re.MULTILINE)]
    assert printed == [page for _, page in outline]
    _, targets = links(synthetic_pdf)
    assert targets[:2 * len(outline)] == [page for _, page in outline for _ in range(2)]


def test_every_page_has_the_header_and_page_x_of_y(synthetic_pdf: bytes) -> None:
    texts = pages_text(synthetic_pdf)
    for number, text in enumerate(texts, start=1):
        assert APP_NAME in text
        assert "CropScan: AI crop disease detection" in text
        assert f"Page {number} of {len(texts)}" in text
        assert "Generated 2026-11-16" in text


def test_citations_link_to_the_sources_and_source_links_are_web_addresses(synthetic: ReportDocument,
                                                                          synthetic_pdf: bytes) -> None:
    reader = PdfReader(BytesIO(synthetic_pdf))
    sources_page = next(reader.get_destination_page_number(item) + 1 for item in reader.outline if item.title == "Sources")
    uris, targets = links(synthetic_pdf)
    assert uris == [entry.url for entry in synthetic.bibliography if entry.url]
    citations = targets[2 * len(reader.outline):]
    assert citations and set(citations) <= {sources_page, sources_page + 1}
    text = squeeze("".join(pages_text(synthetic_pdf)))
    for entry in synthetic.bibliography:
        assert squeeze(f"[{entry.number}] {entry.title}") in text


def test_labels_symbols_and_words_appear_as_text(synthetic_pdf: bytes) -> None:
    text = squeeze("".join(pages_text(synthetic_pdf)))
    for expected in ("[AI interpretation]", "[Sourced]", "[From your idea]", "[Assumption]", "+ Evidence found", "? Unclear",
                     "\u2013 No evidence found in the sources", "Note: AI-assisted analysis", "Caveat:", "High", "Medium"):
        assert squeeze(expected) in text, expected


def test_table_headers_repeat_on_every_page_a_table_spans(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.sections[1].blocks = [TableBlock(caption="Long table", columns=["Row label", "Count"],
                                              rows=[[f"Row {index}", str(index)] for index in range(160)],
                                              col_align=["left", "right"])]
    texts = pages_text(render_report_pdf(document, font_dir=fonts))
    holding = [text for text in texts if re.search(r"^Row \d+", text, flags=re.MULTILINE)]
    assert len(holding) >= 2
    assert all("Row label" in text and "Count" in text for text in holding)
    assert "Row 0" in holding[0] and "Row 159" in holding[-1]


def test_currency_symbols_and_accented_letters_survive(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.sections[1].blocks = [ParagraphBlock(text=CHARACTERS)]
    text = squeeze("".join(pages_text(render_report_pdf(document, font_dir=fonts))))
    assert squeeze(CHARACTERS) in text


def test_identical_input_gives_identical_bytes(synthetic: ReportDocument, synthetic_pdf: bytes, fonts: Path) -> None:
    assert render_report_pdf(synthetic, font_dir=fonts) == synthetic_pdf
    assert render_report_pdf(synthetic.model_copy(deep=True), font_dir=fonts) == synthetic_pdf


def test_the_metadata_names_the_product_and_nothing_personal(synthetic_pdf: bytes, fonts: Path) -> None:
    metadata = PdfReader(BytesIO(synthetic_pdf)).metadata
    assert (metadata.title, metadata.subject, metadata.creator, metadata.author) == (APP_NAME, APP_NAME, APP_NAME, "anonymous")
    values = " ".join(str(value) for value in metadata.values())
    for private in (str(fonts), str(Path.home()), str(ROOT), "\\", "Users"):
        assert private not in values
    assert str(fonts).encode() not in synthetic_pdf and fonts.name.encode() not in synthetic_pdf


def test_only_the_configured_fonts_are_used(synthetic_pdf: bytes) -> None:
    reader = PdfReader(BytesIO(synthetic_pdf))
    used = set()
    for page in reader.pages:
        for _, font in (page["/Resources"].get("/Font") or {}).items():
            font = font.get_object()
            used.add((str(font["/Subtype"]), str(font["/BaseFont"]).split("+", 1)[-1]))
    assert used == {("/TrueType", "BitstreamVeraSans-Roman"), ("/TrueType", "BitstreamVeraSans-Bold"),
                    ("/TrueType", "BitstreamVeraSans-Oblique")}


def test_hostile_text_in_every_block_type_is_printed_literally(fonts: Path) -> None:
    document = hostile_document()
    pdf = render_report_pdf(document, font_dir=fonts)
    texts = pages_text(pdf)
    text = squeeze("".join(texts))
    assert text.count(squeeze(HOSTILE)) >= 7
    for literal in ("</para>", "<br/>", "<i>evil</i>"):
        assert literal in text
    uris, _ = links(pdf)
    assert all(uri.startswith(("http://", "https://")) for uri in uris)
    assert not any("javascript" in uri for uri in uris)


def test_only_web_addresses_become_links(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.bibliography[0] = BibEntry.model_construct(**{**document.bibliography[0].model_dump(), "url": "javascript:alert(1)"})
    document.bibliography[1] = BibEntry.model_construct(**{**document.bibliography[1].model_dump(),
                                                           "url": 'https://example.org/"><script>'})
    pdf = render_report_pdf(document, font_dir=fonts)
    uris, _ = links(pdf)
    assert uris == [entry.url for entry in document.bibliography[2:] if entry.url]
    text = squeeze("".join(pages_text(pdf)))
    assert "javascript:alert(1)" in text and squeeze('https://example.org/"><script>') in text


def test_a_planted_key_is_reported_by_the_consistency_checks_and_never_breaks_the_pdf(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.sections[2].blocks.append(ParagraphBlock(text=f"key {FAKE_KEY}"))
    checked = with_consistency(document, synthetic_complete())
    assert next(check for check in checked.meta.consistency.checks if check.id == "C-11").passed is False
    assert PdfReader(BytesIO(render_report_pdf(checked, font_dir=fonts))).pages


def test_more_than_the_page_cap_stops_with_a_plain_error(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.sections[1].blocks = [ParagraphBlock(text=f"Paragraph {index} " + "text " * 60) for index in range(1500)]
    with pytest.raises(ReportTooLargeError) as raised:
        render_report_pdf(document, font_dir=fonts)
    assert raised.value.code == "report_too_large" and raised.value.status_code == 422
    assert raised.value.user_message == (
        "The report is longer than 60 pages, so the PDF was not made. Markdown and JSON are available."
    )


def test_a_block_that_cannot_fit_on_a_page_stops_with_a_plain_error(fonts: Path) -> None:
    document = full_document(synthetic_complete())
    document.sections[1].blocks = [TableBlock(caption="Huge", columns=[f"Column {index}" for index in range(10)],
                                              rows=[["word " * 4000, *[""] * 9]])]
    with pytest.raises(ReportRenderError) as raised:
        render_report_pdf(document, font_dir=fonts)
    assert raised.value.code == "report_render_failed"
    assert raised.value.user_message == "The PDF could not be laid out. Markdown and JSON are available."


def test_missing_fonts_fail_with_a_plain_error_naming_the_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                synthetic: ReportDocument) -> None:
    monkeypatch.setenv("REPORT_FONT_DIR", str(tmp_path))
    assert missing_font_files() == FONT_NAMES
    with pytest.raises(ReportRenderError) as raised:
        render_report_pdf(synthetic)
    assert raised.value.code == "report_render_failed" and raised.value.status_code == 500
    assert raised.value.user_message == (
        "The report fonts are not installed. See the setup guide. Missing: IBMPlexSans-Regular.ttf, IBMPlexSans-Bold.ttf, "
        "IBMPlexSans-Italic.ttf, IBMPlexMono-Regular.ttf."
    )
    assert str(tmp_path) not in raised.value.user_message
    assert render_report_md(synthetic) and synthetic.model_dump_json()


def test_one_missing_font_is_named_and_never_replaced(tmp_path: Path, synthetic: ReportDocument) -> None:
    folder = bundled_fonts(tmp_path / "fonts")
    (folder / "IBMPlexSans-Italic.ttf").unlink()
    assert missing_font_files(folder) == ["IBMPlexSans-Italic.ttf"]
    with pytest.raises(ReportRenderError) as raised:
        render_report_pdf(synthetic, font_dir=folder)
    assert raised.value.user_message.endswith("Missing: IBMPlexSans-Italic.ttf.")


@pytest.mark.parametrize("content", [b"", b"not a font" * 20, b"\x00\x01\x00\x00" + b"\x00" * 8])
def test_an_unreadable_font_fails_with_a_plain_error(tmp_path: Path, synthetic: ReportDocument, content: bytes) -> None:
    folder = bundled_fonts(tmp_path / "fonts")
    (folder / "IBMPlexSans-Bold.ttf").write_bytes(content)
    with pytest.raises(ReportRenderError) as raised:
        render_report_pdf(synthetic, font_dir=folder)
    assert raised.value.user_message == (
        "The report fonts could not be read. See the setup guide. Unreadable: IBMPlexSans-Bold.ttf."
    )


def test_production_fonts_come_from_assets_fonts_unless_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("REPORT_FONT_DIR", raising=False)
    assert get_settings().report_font_dir == ROOT / "assets" / "fonts"
    monkeypatch.setenv("REPORT_FONT_DIR", "custom/fonts")
    assert get_settings().report_font_dir == ROOT / "custom" / "fonts"
    monkeypatch.setenv("REPORT_FONT_DIR", str(tmp_path))
    assert get_settings().report_font_dir == tmp_path


def test_the_env_example_documents_the_font_folder() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "# REPORT_FONT_DIR=assets/fonts" in lines


def test_reportlab_is_pinned_to_the_installed_version() -> None:
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert f"reportlab=={reportlab.Version}" in lines
    assert any(line.startswith("pypdf>=") for line in lines)


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_every_synthetic_fixture_renders(name: str, fonts: Path) -> None:
    document = full_document(SYNTHETIC_RESULTS[name]())
    reader = PdfReader(BytesIO(render_report_pdf(document, font_dir=fonts)))
    assert len(reader.pages) <= PAGE_CAP
    text = squeeze("".join(page.extract_text() for page in reader.pages))
    for missing in document.meta.sections_missing:
        assert squeeze(f"Not included: {missing.reason}") in text


@pytest.mark.parametrize("path", [*SAVED, *LIVE], ids=lambda path: path.name)
def test_every_stored_result_renders(path: Path, fonts: Path) -> None:
    result: PipelineResult = load(path)
    document = full_document(result)
    reader = PdfReader(BytesIO(render_report_pdf(document, font_dir=fonts)))
    assert 1 < len(reader.pages) <= PAGE_CAP
    assert [item.title for item in reader.outline][-2:] == ["Appendix A: Run details", "Appendix B: Terms"]
