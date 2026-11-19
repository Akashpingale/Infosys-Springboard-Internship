import html
import re
from collections.abc import Iterable

from agents.report_sections import BASIS_LABELS
from models.report import (
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    FactsBlock,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    ReportSection,
    SubheadingBlock,
    TableBlock,
)

COVER_SECTION = "cover"
SOURCES_SECTION = "sources"
CALLOUT_LABELS = {"note": "Note", "caveat": "Caveat", "warning": "Warning"}
SOURCES_COLUMN = "Sources"
CITED_IN = "Cited in: {sections}."
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INLINE = re.compile(r"([\\`*_\[\]|~$#])")
_LEADING_MARK = re.compile(r"^([+=-])")
_LEADING_NUMBER = re.compile(r"^(\d+)([.)])")
_URL = re.compile(r"https?://[^\s<>\"'`\\\x00-\x1f\x7f]+", re.IGNORECASE)


def clean(text: object) -> str:
    return " ".join(_CONTROL.sub(" ", str(text or "")).split())


def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    return url if _URL.fullmatch(url) else None


def escape_inline(text: object) -> str:
    return _INLINE.sub(r"\\\1", html.escape(clean(text), quote=False))


def escape_md(text: object) -> str:
    escaped = _LEADING_MARK.sub(r"\\\1", escape_inline(text))
    return _LEADING_NUMBER.sub(r"\1\\\2", escaped)


def basis_label(basis: str | None) -> str:
    return f"[{BASIS_LABELS[basis]}]" if basis in BASIS_LABELS else ""


def cite_marks(cites: Iterable[int]) -> list[str]:
    return [f"[{number}]" for number in dict.fromkeys(cites)]


def all_sections(document: ReportDocument) -> list[ReportSection]:
    return [*document.sections, *document.appendix_sections]


def section_titles(document: ReportDocument) -> dict[str, str]:
    return {section.id: section.title for section in all_sections(document)}


def cited_in(document: ReportDocument, entry: BibEntry) -> str:
    titles = section_titles(document)
    names = [titles.get(section_id, section_id) for section_id in entry.cited_in]
    return CITED_IN.format(sections=", ".join(names)) if names else ""


def has_row_cites(block: TableBlock) -> bool:
    return any(block.row_cites)


def _labelled(text: str, basis: str | None, cites: Iterable[int]) -> str:
    parts = [escape_md(text), basis_label(basis), *cite_marks(cites)]
    return " ".join(part for part in parts if part)


def _cell(text: str) -> str:
    return escape_inline(text) or " "


def _table(block: TableBlock) -> list[str]:
    columns = list(block.columns)
    rows = [list(row) for row in block.rows]
    align = list(block.col_align) or ["left"] * len(columns)
    marks = [list(cites) for cites in block.row_cites] if block.row_cites else [[] for _ in rows]
    if has_row_cites(block):
        columns.append(SOURCES_COLUMN)
        align.append("left")
        rows = [[*row, " ".join(cite_marks(cites))] for row, cites in zip(rows, marks)]
    lines = [f"**{escape_inline(block.caption)}**", "", "| " + " | ".join(_cell(name) for name in columns) + " |"]
    lines.append("| " + " | ".join("---:" if side == "right" else "---" for side in align) + " |")
    lines += ["| " + " | ".join(_cell(cell) if index < len(block.columns) else cell or " " for index, cell in enumerate(row)) + " |"
              for row in rows]
    return lines


def block_lines(block: ReportBlock) -> list[str]:
    if isinstance(block, ParagraphBlock):
        return [_labelled(block.text, block.basis, block.cites)]
    if isinstance(block, BulletsBlock):
        return [f"- {_labelled(entry.text, entry.basis, entry.cites)}" for entry in block.items]
    if isinstance(block, TableBlock):
        return _table(block)
    if isinstance(block, CalloutBlock):
        return [f"> **{CALLOUT_LABELS[block.kind]}:** {escape_inline(block.text)}"]
    if isinstance(block, FactsBlock):
        return [f"- **{escape_inline(pair.label)}:** {escape_inline(pair.value)}" for pair in block.pairs]
    if isinstance(block, SubheadingBlock):
        return [f"### {escape_inline(block.text)}"]
    return []


def bibliography_line(document: ReportDocument, entry: BibEntry) -> str:
    parts = [escape_md(entry.title)]
    if entry.domain:
        parts.append(f"({escape_inline(entry.domain)})")
    url = safe_url(entry.url)
    if url is not None:
        parts.append(f"<{url}>")
    elif entry.url:
        parts.append(escape_inline(entry.url))
    where = cited_in(document, entry)
    if where:
        parts.append(escape_inline(where))
    return f"{entry.number}. " + " ".join(parts)


def render_report_md(document: ReportDocument) -> str:
    lines = [f"# {escape_inline(document.title)}", "", escape_md(document.subtitle), ""]
    for section in all_sections(document):
        if section.id != COVER_SECTION:
            lines += [f"## {escape_inline(section.title)}", ""]
        for block in section.blocks:
            lines += [*block_lines(block), ""]
        if section.id == SOURCES_SECTION and document.bibliography:
            lines += [*(bibliography_line(document, entry) for entry in document.bibliography), ""]
    return "\n".join(lines).rstrip("\n") + "\n"
