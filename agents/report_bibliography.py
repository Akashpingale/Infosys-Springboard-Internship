from dataclasses import dataclass, field

from agents.evidence import domain_of, is_summary_id, normalize_url
from agents.report_sections import CATALOGUE_IDS, not_included, source_key
from models.report import (
    REPORT_ANALYSES,
    BibEntry,
    BulletsBlock,
    CalloutBlock,
    MissingSection,
    ParagraphBlock,
    ReportDocument,
    TableBlock,
)
from models.schemas import PipelineResult

SUMMARY_TITLE = "Search engine summary (generated, not a page)"
SUMMARY_IDENTITY = "summary"
BIBLIOGRAPHY_CAP = 100
CAP_NOTE = "Only the first {cap} sources are listed. Later citations are not numbered."
REASON_NO_SOURCES = "No sources were cited in this report."
SOURCES_SECTION = "sources"


@dataclass
class Page:
    identity: str
    title: str
    url: str | None
    has_page: bool


@dataclass
class Entry:
    page: Page
    number: int
    analyses: list[str] = field(default_factory=list)
    cited_in: list[str] = field(default_factory=list)


def web_url(url: str) -> str | None:
    clean = url.strip()
    return clean if clean.lower().startswith(("http://", "https://")) else None


def source_pages(result: PipelineResult) -> dict[str, Page]:
    pages: dict[str, Page] = {}
    for analysis in REPORT_ANALYSES:
        model = getattr(result, analysis)
        for source in model.sources if model is not None else []:
            key = source_key(analysis, source.id)
            if key in pages:
                continue
            if is_summary_id(source.id):
                pages[key] = Page(SUMMARY_IDENTITY, SUMMARY_TITLE, None, False)
                continue
            url = web_url(source.url)
            identity = normalize_url(url) if url else key
            pages[key] = Page(identity, source.title.strip() or (domain_of(url) if url else source.id), url, True)
    return pages


class Numbering:
    def __init__(self, pages: dict[str, Page], cap: int) -> None:
        self.pages = pages
        self.cap = cap
        self.entries: dict[str, Entry] = {}
        self.capped = False

    def cite(self, keys: list[str], section_id: str) -> list[int]:
        numbers: list[int] = []
        for key in keys:
            page = self.pages.get(key)
            if page is None:
                continue
            entry = self.entries.get(page.identity)
            if entry is None:
                if len(self.entries) >= self.cap:
                    self.capped = True
                    continue
                entry = Entry(page, len(self.entries) + 1)
                self.entries[page.identity] = entry
            analysis = key.split(":", 1)[0]
            if analysis not in entry.analyses:
                entry.analyses.append(analysis)
            if section_id not in entry.cited_in:
                entry.cited_in.append(section_id)
            if entry.number not in numbers:
                numbers.append(entry.number)
        return numbers

    def bibliography(self) -> list[BibEntry]:
        return [
            BibEntry(
                number=entry.number,
                title=entry.page.title,
                url=entry.page.url,
                domain=domain_of(entry.page.url) if entry.page.url else "",
                analyses=[name for name in REPORT_ANALYSES if name in entry.analyses],
                cited_in=list(entry.cited_in),
                has_page=entry.page.has_page,
            )
            for entry in self.entries.values()
        ]


def number_citations(document: ReportDocument, result: PipelineResult, *, cap: int = BIBLIOGRAPHY_CAP) -> ReportDocument:
    numbered = document.model_copy(deep=True)
    numbering = Numbering(source_pages(result), cap)
    for section in [*numbered.sections, *numbered.appendix_sections]:
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                block.cites = numbering.cite(block.keys, section.id)
                block.keys = []
            elif isinstance(block, BulletsBlock):
                for entry in block.items:
                    entry.cites = numbering.cite(entry.keys, section.id)
                    entry.keys = []
            elif isinstance(block, TableBlock):
                block.row_cites = [numbering.cite(keys, section.id) for keys in block.row_keys] if block.row_keys else []
                block.row_keys = []
    numbered.bibliography = numbering.bibliography()
    sources = next(section for section in numbered.sections if section.id == SOURCES_SECTION)
    if not numbered.bibliography:
        sources.blocks = not_included(REASON_NO_SOURCES)
        meta = numbered.meta
        meta.sections_included = [section_id for section_id in meta.sections_included if section_id != SOURCES_SECTION]
        missing = [entry for entry in meta.sections_missing if entry.id != SOURCES_SECTION]
        missing.append(MissingSection(id=SOURCES_SECTION, reason=REASON_NO_SOURCES))
        meta.sections_missing = sorted(missing, key=lambda entry: CATALOGUE_IDS.index(entry.id))
    elif numbering.capped:
        sources.blocks = [CalloutBlock(kind="note", text=CAP_NOTE.format(cap=cap))]
    return numbered
