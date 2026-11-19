import hashlib
import struct
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import IndexingFlowable, LayoutError
from reportlab.platypus.tableofcontents import TableOfContents

from config import get_settings
from models.report import (
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    FactsBlock,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    SubheadingBlock,
    TableBlock,
)
from utils.errors import ReportRenderError, ReportTooLargeError
from utils.report_render_md import (
    CALLOUT_LABELS,
    COVER_SECTION,
    SOURCES_COLUMN,
    SOURCES_SECTION,
    basis_label,
    cited_in,
    clean,
    has_row_cites,
    safe_url,
)

FONT_FILES = (
    ("regular", "IBMPlexSans-Regular.ttf"),
    ("bold", "IBMPlexSans-Bold.ttf"),
    ("italic", "IBMPlexSans-Italic.ttf"),
    ("mono", "IBMPlexMono-Regular.ttf"),
)
PAGE_CAP = 60
ACCENT = colors.HexColor("#0369A1")
RULE = colors.HexColor("#B8B8B8")
MUTED = colors.HexColor("#4D4D4D")
MARGIN = 20 * mm
PAGE_WIDTH, PAGE_HEIGHT = A4
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN
GENERIC_AUTHOR = "anonymous"
CONTENTS_TITLE = "Contents"
FOOTER_PAGE = "Page {page} of {total}"
FOOTER_DATE = "Generated {date}"
MSG_FONTS_MISSING = ReportRenderError.default_message + " Missing: {files}."
MSG_FONTS_UNREADABLE = "The report fonts could not be read. See the setup guide. Unreadable: {file}."
MSG_TOO_LARGE = f"The report is longer than {PAGE_CAP} pages, so the PDF was not made. Markdown and JSON are available."
MSG_LAYOUT = "The PDF could not be laid out. Markdown and JSON are available."
PAGE_EVENT = "ReportPage"


class PageCapReached(Exception):
    pass


def product_name() -> str:
    from routes.meta_routes import APP_NAME

    return APP_NAME


def font_directory(font_dir: Path | str | None = None) -> Path:
    return Path(font_dir) if font_dir is not None else get_settings().report_font_dir


def missing_font_files(font_dir: Path | str | None = None) -> list[str]:
    folder = font_directory(font_dir)
    return [name for _, name in FONT_FILES if not (folder / name).is_file()]


def load_fonts(font_dir: Path | str | None = None) -> dict[str, str]:
    folder = font_directory(font_dir)
    missing = missing_font_files(folder)
    if missing:
        raise ReportRenderError(MSG_FONTS_MISSING.format(files=", ".join(missing)))
    names: dict[str, str] = {}
    registered = set(pdfmetrics.getRegisteredFontNames())
    for role, file_name in FONT_FILES:
        data = (folder / file_name).read_bytes()
        name = f"Report-{role}-{hashlib.sha256(data).hexdigest()[:16]}"
        if name not in registered:
            try:
                pdfmetrics.registerFont(TTFont(name, BytesIO(data)))
            except (TTFError, struct.error, OSError, ValueError, KeyError, IndexError):
                raise ReportRenderError(MSG_FONTS_UNREADABLE.format(file=file_name)) from None
        names[role] = name
    return names


def pdf_text(text: object) -> str:
    return escape(clean(text))


def pdf_href(url: str) -> str:
    return escape(url, {'"': "&quot;"})


class Styles:
    def __init__(self, fonts: dict[str, str]) -> None:
        self.fonts = fonts
        regular, bold = fonts["regular"], fonts["bold"]
        self.title = ParagraphStyle("title", fontName=bold, fontSize=22, leading=28, textColor=ACCENT, spaceAfter=6)
        self.subtitle = ParagraphStyle("subtitle", fontName=regular, fontSize=14, leading=19, spaceAfter=12)
        self.section = ParagraphStyle("section", fontName=bold, fontSize=15, leading=20, textColor=ACCENT, spaceBefore=14,
                                      spaceAfter=6, keepWithNext=1)
        self.subheading = ParagraphStyle("subheading", fontName=bold, fontSize=11, leading=15, spaceBefore=8, spaceAfter=3,
                                         keepWithNext=1)
        self.body = ParagraphStyle("body", fontName=regular, fontSize=10, leading=14, spaceAfter=5)
        self.bullet = ParagraphStyle("bullet", parent=self.body, leftIndent=12, bulletIndent=2, spaceAfter=3,
                                     bulletFontName=regular)
        self.caption = ParagraphStyle("caption", fontName=fonts["italic"], fontSize=9, leading=12, spaceBefore=4, spaceAfter=3,
                                      keepWithNext=1)
        self.cell = ParagraphStyle("cell", fontName=regular, fontSize=8, leading=10, alignment=TA_LEFT)
        self.cell_right = ParagraphStyle("cell_right", parent=self.cell, alignment=TA_RIGHT)
        self.head = ParagraphStyle("head", parent=self.cell, fontName=bold)
        self.head_right = ParagraphStyle("head_right", parent=self.head, alignment=TA_RIGHT)
        self.label = ParagraphStyle("label", fontName=bold, fontSize=9, leading=12)
        self.value = ParagraphStyle("value", fontName=regular, fontSize=9, leading=12)
        self.callout = ParagraphStyle("callout", fontName=regular, fontSize=9.5, leading=13)
        self.source = ParagraphStyle("source", fontName=regular, fontSize=9, leading=12, leftIndent=18, firstLineIndent=-18)
        self.contents = [ParagraphStyle("contents", fontName=regular, fontSize=10, leading=15)]


class Heading(Paragraph):
    def __init__(self, text: str, style: ParagraphStyle, key: str) -> None:
        super().__init__(text, style)
        self.toc_key = key
        self.toc_text = text


class PageTotal(IndexingFlowable):
    def __init__(self) -> None:
        super().__init__()
        self.total = 0
        self.counted = 0
        self.settled = False

    def beforeBuild(self) -> None:
        self.counted = 0

    def notify(self, kind: str, stuff: object) -> None:
        if kind == PAGE_EVENT and isinstance(stuff, int):
            self.counted = max(self.counted, stuff)

    def afterBuild(self) -> None:
        self.settled = self.counted == self.total
        self.total = self.counted

    def isSatisfied(self) -> bool:
        return self.settled

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        pass


class ReportTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable: Flowable) -> None:
        key = getattr(flowable, "toc_key", None)
        if key is None:
            return
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(clean(flowable.getPlainText()), key, level=0)
        self.notify("TOCEntry", (0, flowable.toc_text, self.page, key))

    def afterPage(self) -> None:
        self.notify(PAGE_EVENT, self.page)


def table_style(fonts: dict[str, str], *commands: tuple) -> TableStyle:
    return TableStyle([("FONTNAME", (0, 0), (-1, -1), fonts["regular"]), *commands])


def fitted(text: str, font: str, size: float, width: float) -> str:
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "\u2026", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "\u2026"


def suffix(styles: Styles, basis: str | None, cites: list[int]) -> str:
    parts = []
    label = basis_label(basis)
    if label:
        parts.append(f'<font name="{styles.fonts["italic"]}">{pdf_text(label)}</font>')
    parts += [f'<a href="#source-{number}" color="#0369A1">[{number}]</a>' for number in dict.fromkeys(cites)]
    return (" " + " ".join(parts)) if parts else ""


def column_widths(columns: list[str], rows: list[list[str]], width: float) -> list[float]:
    weights = []
    for index, name in enumerate(columns):
        cells = [clean(name), *(clean(row[index]) for row in rows)]
        average = sum(len(cell) for cell in cells) / len(cells)
        longest = max((len(word) for cell in cells for word in cell.split()), default=1)
        weights.append(max(min(average, 60.0), min(longest, 14), 3.0))
    total = sum(weights)
    return [width * weight / total for weight in weights]


def table_flowables(block: TableBlock, styles: Styles) -> list[Flowable]:
    columns = list(block.columns)
    rows = [list(row) for row in block.rows]
    align = list(block.col_align) or ["left"] * len(columns)
    cites: list[list[int]] = [list(entry) for entry in block.row_cites] if block.row_cites else [[] for _ in rows]
    with_sources = has_row_cites(block)
    if with_sources:
        columns.append(SOURCES_COLUMN)
        align.append("left")
    widths = column_widths(columns, [[*row, " ".join(f"[{n}]" for n in marks)] if with_sources else row
                                     for row, marks in zip(rows, cites)], TEXT_WIDTH)
    head = [Paragraph(pdf_text(name), styles.head_right if side == "right" else styles.head) for name, side in zip(columns, align)]
    body = []
    for row, marks in zip(rows, cites):
        cells = [Paragraph(pdf_text(cell), styles.cell_right if side == "right" else styles.cell) for cell, side in zip(row, align)]
        if with_sources:
            cells.append(Paragraph(suffix(styles, None, marks).strip(), styles.cell))
        body.append(cells)
    table = Table([head, *body], colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(table_style(
        styles.fonts,
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ))
    return [Paragraph(pdf_text(block.caption), styles.caption), table, Spacer(1, 6)]


def callout_flowable(block: CalloutBlock, styles: Styles) -> Flowable:
    text = f'<font name="{styles.fonts["bold"]}">{CALLOUT_LABELS[block.kind]}:</font> {pdf_text(block.text)}'
    box = Table([[Paragraph(text, styles.callout)]], colWidths=[TEXT_WIDTH], hAlign="LEFT")
    box.setStyle(table_style(
        styles.fonts,
        ("LINEBEFORE", (0, 0), (0, 0), 2, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ))
    return KeepTogether([box, Spacer(1, 6)])


def facts_flowable(block: FactsBlock, styles: Styles) -> Flowable:
    if not block.pairs:
        return Spacer(1, 0)
    rows = [[Paragraph(pdf_text(pair.label), styles.label), Paragraph(pdf_text(pair.value), styles.value)] for pair in block.pairs]
    table = Table(rows, colWidths=[TEXT_WIDTH * 0.32, TEXT_WIDTH * 0.68], hAlign="LEFT")
    table.setStyle(table_style(
        styles.fonts,
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ))
    return KeepTogether([table, Spacer(1, 6)]) if len(rows) <= 12 else table


def block_flowables(block: ReportBlock, styles: Styles) -> list[Flowable]:
    if isinstance(block, ParagraphBlock):
        return [Paragraph(pdf_text(block.text) + suffix(styles, block.basis, block.cites), styles.body)]
    if isinstance(block, BulletsBlock):
        return [Paragraph(pdf_text(entry.text) + suffix(styles, entry.basis, entry.cites), styles.bullet, bulletText="\u2022")
                for entry in block.items]
    if isinstance(block, TableBlock):
        return table_flowables(block, styles)
    if isinstance(block, CalloutBlock):
        return [callout_flowable(block, styles)]
    if isinstance(block, FactsBlock):
        return [facts_flowable(block, styles)]
    if isinstance(block, SubheadingBlock):
        return [Paragraph(pdf_text(block.text), styles.subheading)]
    return []


def source_flowable(document: ReportDocument, entry: BibEntry, styles: Styles) -> Flowable:
    head = f'<a name="source-{entry.number}"/>[{entry.number}] {pdf_text(entry.title)}'
    if entry.domain:
        head += f" ({pdf_text(entry.domain)})"
    lines = [head]
    url = safe_url(entry.url)
    if url is not None:
        lines.append(f'<a href="{pdf_href(url)}" color="#0369A1"><font name="{styles.fonts["mono"]}">{pdf_text(url)}</font></a>')
    elif entry.url:
        lines.append(pdf_text(entry.url))
    where = cited_in(document, entry)
    if where:
        lines.append(pdf_text(where))
    return KeepTogether([Paragraph("<br/>".join(lines), styles.source), Spacer(1, 4)])


def story(document: ReportDocument, styles: Styles, pages: PageTotal) -> list[Flowable]:
    flowables: list[Flowable] = [pages, Paragraph(pdf_text(document.title), styles.title),
                                 Paragraph(pdf_text(document.subtitle), styles.subtitle)]
    cover = next((section for section in document.sections if section.id == COVER_SECTION), None)
    for block in cover.blocks if cover is not None else []:
        flowables += block_flowables(block, styles)
    contents = TableOfContents(levelStyles=styles.contents, dotsMinLevel=0,
                               tableStyle=table_style(styles.fonts, ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                                      ("RIGHTPADDING", (0, 0), (-1, -1), 0)))
    flowables += [Spacer(1, 10), Paragraph(CONTENTS_TITLE, styles.section), contents, PageBreak()]
    for section in document.sections:
        if section.id == COVER_SECTION:
            continue
        flowables += [CondPageBreak(40 * mm), Heading(pdf_text(section.title), styles.section, f"section-{section.id}")]
        for block in section.blocks:
            flowables += block_flowables(block, styles)
        if section.id == SOURCES_SECTION:
            flowables += [source_flowable(document, entry, styles) for entry in document.bibliography]
    for index, section in enumerate(document.appendix_sections):
        flowables += [PageBreak() if index == 0 else CondPageBreak(40 * mm),
                      Heading(pdf_text(section.title), styles.section, f"section-{section.id}")]
        for block in section.blocks:
            flowables += block_flowables(block, styles)
    return flowables


def render_report_pdf(document: ReportDocument, *, font_dir: Path | str | None = None) -> bytes:
    fonts = load_fonts(font_dir)
    styles = Styles(fonts)
    name = product_name()
    idea = clean(document.meta.idea_title)
    date = clean(document.meta.generated_at)[:10]

    pages = PageTotal()

    def decorate(canvas: Canvas, doc: BaseDocTemplate) -> None:
        if doc.page > PAGE_CAP:
            raise PageCapReached
        canvas.saveState()
        canvas.setFont(fonts["regular"], 8)
        canvas.setFillColor(MUTED)
        top = PAGE_HEIGHT - MARGIN + 7 * mm
        canvas.drawString(MARGIN, top, name)
        room = TEXT_WIDTH - pdfmetrics.stringWidth(name, fonts["regular"], 8) - 12 * mm
        canvas.drawRightString(PAGE_WIDTH - MARGIN, top, fitted(idea, fonts["regular"], 8, room))
        bottom = MARGIN - 10 * mm
        canvas.drawString(MARGIN, bottom, FOOTER_DATE.format(date=date))
        canvas.drawRightString(PAGE_WIDTH - MARGIN, bottom, FOOTER_PAGE.format(page=doc.page, total=max(pages.total, doc.page)))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, top - 2 * mm, PAGE_WIDTH - MARGIN, top - 2 * mm)
        canvas.restoreState()

    buffer = BytesIO()
    doc = ReportTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=name,
        subject=name,
        creator=name,
        author=GENERIC_AUTHOR,
        keywords="",
        lang="en",
        invariant=1,
        initialFontName=fonts["regular"],
    )
    frame = Frame(MARGIN, MARGIN, TEXT_WIDTH, PAGE_HEIGHT - 2 * MARGIN, id="text", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=decorate)])
    try:
        doc.multiBuild(story(document, styles, pages))
    except PageCapReached:
        raise ReportTooLargeError(MSG_TOO_LARGE) from None
    except LayoutError:
        raise ReportRenderError(MSG_LAYOUT) from None
    return buffer.getvalue()
