import html
import json
import re
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from agents.report_checks import block_texts
from agents.report_sections import BASIS_LABELS
from models.report import BulletsBlock, ParagraphBlock, ReportDocument, TableBlock, read_report, report_json
from tests.m4_report_fixtures_synthetic import SYNTHETIC_RESULTS
from tests.test_m4_render_pdf import bundled_fonts
from tests.test_m4_report_agent import report_of, use_writer
from utils.report_render_md import cited_in, render_report_md, safe_url
from utils.report_render_pdf import render_report_pdf

_MD_ESCAPE = re.compile(r"\\([\\`*_\[\]|~$#+=\-.)])")


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def screen_texts(document: ReportDocument) -> list[str]:
    texts = [document.title, document.subtitle]
    for section in [*document.sections, *document.appendix_sections]:
        if section.id != "cover":
            texts.append(section.title)
        for block in section.blocks:
            texts += block_texts(block)
            if isinstance(block, ParagraphBlock):
                texts += [f"[{BASIS_LABELS[block.basis]}]" if block.basis else "", *(f"[{n}]" for n in block.cites)]
            elif isinstance(block, BulletsBlock):
                texts += [f"[{BASIS_LABELS[item.basis]}]" if item.basis else "" for item in block.items]
                texts += [f"[{n}]" for item in block.items for n in item.cites]
            elif isinstance(block, TableBlock):
                texts += [f"[{n}]" for row in block.row_cites for n in row]
    for entry in document.bibliography:
        texts += [f"[{entry.number}]", entry.title, entry.domain, safe_url(entry.url) or "", cited_in(document, entry)]
    return [text for text in texts if text.strip()]


def markdown_plain(text: str) -> str:
    return squeeze(html.unescape(_MD_ESCAPE.sub(r"\1", text)))


def pdf_plain(pdf: bytes) -> str:
    return squeeze("".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages))


@pytest.fixture(scope="module")
def fonts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return bundled_fonts(tmp_path_factory.mktemp("cross-format-fonts"))


@pytest.fixture(scope="module")
def documents() -> dict[str, ReportDocument]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        use_writer(monkeypatch)
        return {name: report_of(factory()) for name, factory in SYNTHETIC_RESULTS.items()}


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_screen_markdown_and_pdf_hold_the_same_text(name: str, documents: dict[str, ReportDocument], fonts: Path) -> None:
    document = documents[name]
    screen = read_report(json.loads(report_json(document)))
    markdown = markdown_plain(render_report_md(document))
    pdf = pdf_plain(render_report_pdf(document, font_dir=fonts))
    expected = screen_texts(screen)
    assert expected == screen_texts(document)
    missing_md = [text for text in expected if squeeze(text) not in markdown]
    missing_pdf = [text for text in expected if squeeze(text) not in pdf]
    assert (missing_md, missing_pdf) == ([], [])


@pytest.mark.parametrize("name", list(SYNTHETIC_RESULTS))
def test_the_json_download_is_the_document_unmodified(name: str, documents: dict[str, ReportDocument]) -> None:
    document = documents[name]
    data = json.loads(report_json(document))
    assert data == document.model_dump(mode="json")
    assert read_report(data) == document


def test_the_three_formats_come_from_one_document_and_agree_on_its_order(documents: dict[str, ReportDocument],
                                                                         fonts: Path) -> None:
    document = documents["complete"]
    titles = [section.title for section in [*document.sections, *document.appendix_sections] if section.id != "cover"]
    markdown = [line[3:] for line in render_report_md(document).splitlines() if line.startswith("## ")]
    reader = PdfReader(BytesIO(render_report_pdf(document, font_dir=fonts)))
    assert markdown == titles == [item.title for item in reader.outline]
