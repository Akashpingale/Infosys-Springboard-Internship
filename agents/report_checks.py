import re
from collections.abc import Iterable, Iterator

from agents.report_sections import (
    CATALOGUE_IDS,
    COLUMN_FEATURES,
    COLUMN_NUMBER,
    COLUMN_RISKS,
    DIFFERENTIATOR_LABELS,
    HEADING_CONSISTENCY,
    LABEL_DIFFERENTIATOR,
    LABEL_PRIORITY_SEGMENT,
    LABEL_RUN_STATUS,
    LABEL_TARGET_SEGMENT,
    NOT_INCLUDED,
    RUN_STATUS_LABELS,
    glance_facts,
    missing_reason,
    stage_names,
    unfinished_stages,
)
from agents.strategy_checks import secret_findings
from models.report import (
    BulletsBlock,
    CalloutBlock,
    ConsistencyCheck,
    ConsistencyReport,
    FactPair,
    FactsBlock,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    ReportSection,
    SubheadingBlock,
    TableBlock,
)
from models.schemas import PipelineResult

CHECKS = (
    ("C-01", "Every citation number exists in the bibliography, and every bibliography entry is cited at least once."),
    ("C-02", "Every catalogue section is present or listed as missing with a reason."),
    ("C-03", "Every figure in Validation at a glance equals the value recomputed from the stored result."),
    ("C-04", "The positioning target segment equals the market priority segment when both exist."),
    ("C-05", "Every risk referenced by an MVP feature or a channel exists in the risk register shown."),
    ("C-06", "Every feature referenced by a channel exists in the MVP section shown."),
    ("C-07", "Every gap shown carries the standing caveat, and every hypothesis differentiator is labelled."),
    ("C-08", "No narrative statement is labelled sourced."),
    ("C-09", "Every warning-level notice appears in Limitations."),
    ("C-10", "The run status shown equals the stored status, and a partial run lists the stages that did not finish."),
    ("C-11", "No text contains a configured key value or key-shaped text."),
    ("C-12", "No text contains control characters that could break an output format. Escaping is checked per format when the report is rendered."),
)
DESCRIPTIONS = dict(CHECKS)
CONSISTENCY_LINE = "{passed} of {total} consistency checks passed."
FAILING_LINE = " Failing checks: {ids}."
HYPOTHESIS_MARK = "a hypothesis"
NO_REFERENCE = "None"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normal(text: str) -> str:
    return " ".join(text.split()).casefold()


def all_sections(document: ReportDocument) -> list[ReportSection]:
    return [*document.sections, *document.appendix_sections]


def section(document: ReportDocument, section_id: str) -> ReportSection | None:
    return next((entry for entry in all_sections(document) if entry.id == section_id), None)


def blocks(document: ReportDocument, section_id: str) -> list[ReportBlock]:
    found = section(document, section_id)
    return list(found.blocks) if found is not None else []


def shown(document: ReportDocument, section_id: str) -> bool:
    return section_id in document.meta.sections_included


def fact_value(document: ReportDocument, section_id: str, label: str) -> str | None:
    for block in blocks(document, section_id):
        if isinstance(block, FactsBlock):
            for pair in block.pairs:
                if pair.label == label:
                    return pair.value
    return None


def block_texts(block: ReportBlock) -> list[str]:
    if isinstance(block, (ParagraphBlock, SubheadingBlock, CalloutBlock)):
        return [block.text]
    if isinstance(block, BulletsBlock):
        return [entry.text for entry in block.items]
    if isinstance(block, FactsBlock):
        return [text for pair in block.pairs for text in (pair.label, pair.value)]
    if isinstance(block, TableBlock):
        return [block.caption, *block.columns, *(cell for row in block.rows for cell in row)]
    return []


def block_cites(block: ReportBlock) -> list[int]:
    if isinstance(block, ParagraphBlock):
        return list(block.cites)
    if isinstance(block, BulletsBlock):
        return [number for entry in block.items for number in entry.cites]
    if isinstance(block, TableBlock):
        return [number for row in block.row_cites for number in row]
    return []


def column_values(document: ReportDocument, section_id: str, column: str) -> list[str]:
    values: list[str] = []
    for block in blocks(document, section_id):
        if isinstance(block, TableBlock) and column in block.columns:
            index = block.columns.index(column)
            values += [row[index] for row in block.rows]
    return values


def referenced(cells: Iterable[str]) -> list[str]:
    return [part.strip() for cell in cells for part in cell.split(",") if part.strip() and part.strip() != NO_REFERENCE]


def strings(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, entry in value.items():
            yield from strings(key)
            yield from strings(entry)
    elif isinstance(value, list):
        for entry in value:
            yield from strings(entry)
    elif isinstance(value, str):
        yield value


def outcome(check_id: str, problems: list[str]) -> ConsistencyCheck:
    return ConsistencyCheck(id=check_id, description=DESCRIPTIONS[check_id], passed=not problems, detail="; ".join(problems))


def check_citations(document: ReportDocument) -> list[str]:
    cited = {number for entry in all_sections(document) for block in entry.blocks for number in block_cites(block)}
    listed = [entry.number for entry in document.bibliography]
    problems = []
    unknown = sorted(cited - set(listed))
    if unknown:
        problems.append(f"citations without a source entry: {', '.join(map(str, unknown))}")
    uncited = sorted(set(listed) - cited)
    if uncited:
        problems.append(f"source entries never cited: {', '.join(map(str, uncited))}")
    if len(listed) != len(set(listed)):
        problems.append("a source number is used twice")
    return problems


def check_catalogue(document: ReportDocument) -> list[str]:
    problems = []
    order = [entry.id for entry in all_sections(document)]
    if order != list(CATALOGUE_IDS):
        problems.append("the sections are not the catalogue sections in catalogue order")
    meta = document.meta
    missing = {entry.id: entry.reason for entry in meta.sections_missing}
    for section_id in CATALOGUE_IDS:
        included = section_id in meta.sections_included
        if included == (section_id in missing):
            problems.append(f"{section_id} is not listed exactly once as included or missing")
        if section_id in missing:
            reason = missing[section_id].strip()
            if not reason:
                problems.append(f"{section_id} is missing without a reason")
            texts = [text for block in blocks(document, section_id) for text in block_texts(block)]
            if NOT_INCLUDED.format(reason=reason) not in texts:
                problems.append(f"{section_id} does not say why it is not included")
    return problems


def check_glance(document: ReportDocument, source: PipelineResult) -> list[str]:
    if missing_reason("at_a_glance", source) is not None:
        return [] if not shown(document, "at_a_glance") else ["figures are shown although nothing could be counted"]
    shown_pairs: list[FactPair] = [pair for block in blocks(document, "at_a_glance") if isinstance(block, FactsBlock)
                                   for pair in block.pairs]
    expected = glance_facts(source)
    if [pair.label for pair in shown_pairs] != [pair.label for pair in expected]:
        return ["the figures shown are not the expected figures"]
    return [f"{pair.label} shows {pair.value!r}, expected {want.value!r}"
            for pair, want in zip(shown_pairs, expected) if pair.value != want.value]


def check_segments(document: ReportDocument) -> list[str]:
    priority = fact_value(document, "market", LABEL_PRIORITY_SEGMENT)
    target = fact_value(document, "gtm", LABEL_TARGET_SEGMENT)
    if priority is None or target is None or normal(priority) == normal(target):
        return []
    return [f"target segment {target!r} differs from priority segment {priority!r}"]


def check_risk_links(document: ReportDocument, source: PipelineResult) -> list[str]:
    register = set(column_values(document, "risks", COLUMN_NUMBER)) if shown(document, "risks") else set()
    problems = []
    for section_id in ("mvp", "gtm"):
        unknown = [value for value in referenced(column_values(document, section_id, COLUMN_RISKS)) if value not in register]
        if unknown:
            problems.append(f"{section_id} refers to risks not in the register: {', '.join(unknown)}")
    known = {risk.id for risk in source.swot.risks} if source.swot is not None else set()
    linked = [*(ref for feature in (source.mvp.features if source.mvp else []) for ref in feature.mitigates_risk_ids),
              *(ref for channel in (source.gtm.channels if source.gtm else []) for ref in channel.addresses_risk_ids)]
    absent = sorted(set(linked) - known)
    if absent:
        problems.append(f"the result links {len(absent)} risk id(s) the risk analysis does not hold")
    return problems


def check_feature_links(document: ReportDocument, source: PipelineResult) -> list[str]:
    features = set(column_values(document, "mvp", COLUMN_NUMBER)) if shown(document, "mvp") else set()
    problems = []
    unknown = [value for value in referenced(column_values(document, "gtm", COLUMN_FEATURES)) if value not in features]
    if unknown:
        problems.append(f"channels refer to features not in the MVP section: {', '.join(unknown)}")
    known = {feature.id for feature in source.mvp.features} if source.mvp is not None else set()
    linked = {ref for channel in (source.gtm.channels if source.gtm else []) for ref in channel.uses_feature_ids}
    if linked - known:
        problems.append(f"the result links {len(linked - known)} feature id(s) the MVP plan does not hold")
    return problems


def check_hypotheses(document: ReportDocument, source: PipelineResult) -> list[str]:
    problems = []
    competitors = source.competitors
    if competitors is not None and competitors.market_gaps and shown(document, "competitors"):
        section_blocks = blocks(document, "competitors")
        caveats = {normal(block.text) for block in section_blocks if isinstance(block, CalloutBlock) and block.kind == "caveat"}
        if any(normal(gap.caveat) not in caveats for gap in competitors.market_gaps):
            problems.append("a gap is shown without its caveat")
        gap_lines = [text for gap in competitors.market_gaps for text in [normal(gap.description)]]
        items = [normal(entry.text) for block in section_blocks if isinstance(block, BulletsBlock) for entry in block.items]
        for line in gap_lines:
            matching = [text for text in items if text.startswith(line)]
            if not matching or not all(HYPOTHESIS_MARK in text for text in matching):
                problems.append("a gap is not labelled as a hypothesis")
                break
    gtm = source.gtm
    if gtm is not None and gtm.positioning.differentiator_status == "hypothesis" and shown(document, "gtm"):
        value = fact_value(document, "gtm", LABEL_DIFFERENTIATOR) or ""
        if DIFFERENTIATOR_LABELS["hypothesis"] not in value:
            problems.append("the differentiator is not labelled as a hypothesis")
    return problems


def check_narrative(document: ReportDocument) -> list[str]:
    count = 0
    for entry in all_sections(document):
        for block in entry.blocks:
            if isinstance(block, ParagraphBlock) and block.narrative and block.basis == "sourced":
                count += 1
            elif isinstance(block, BulletsBlock) and block.narrative:
                count += sum(1 for item in block.items if item.basis == "sourced")
    return [f"{count} narrative statement(s) are labelled sourced"] if count else []


def check_notices(document: ReportDocument, source: PipelineResult) -> list[str]:
    texts = {normal(text) for block in blocks(document, "limitations") for text in block_texts(block)}
    absent = [notice.code for notice in source.notices if notice.severity == "warning" and normal(notice.message) not in texts]
    return [f"warning notices not in Limitations: {', '.join(dict.fromkeys(absent))}"] if absent else []


def check_status(document: ReportDocument, source: PipelineResult) -> list[str]:
    problems = []
    if document.meta.run_status != source.status:
        problems.append("the stored status differs from the report's")
    if fact_value(document, "cover", LABEL_RUN_STATUS) != RUN_STATUS_LABELS[source.status]:
        problems.append("the title block does not show the stored status")
    unfinished = stage_names(unfinished_stages(source))
    if source.status == "partial" or unfinished:
        warnings = [block.text for block in blocks(document, "cover") if isinstance(block, CalloutBlock) and block.kind == "warning"]
        if not unfinished or not any(all(name in text for name in unfinished) for text in warnings):
            problems.append("the title block does not list the stages that did not finish")
    return problems


def check_secrets(document: ReportDocument) -> list[str]:
    found = secret_findings(document.model_dump(mode="json"))
    return [f"found {', '.join(found)}"] if found else []


def check_control_characters(document: ReportDocument) -> list[str]:
    count = sum(1 for text in strings(document.model_dump(mode="json")) if _CONTROL.search(text))
    return [f"{count} text(s) hold control characters"] if count else []


def check_document(document: ReportDocument, source: PipelineResult) -> ConsistencyReport:
    checks = [
        outcome("C-01", check_citations(document)),
        outcome("C-02", check_catalogue(document)),
        outcome("C-03", check_glance(document, source)),
        outcome("C-04", check_segments(document)),
        outcome("C-05", check_risk_links(document, source)),
        outcome("C-06", check_feature_links(document, source)),
        outcome("C-07", check_hypotheses(document, source)),
        outcome("C-08", check_narrative(document)),
        outcome("C-09", check_notices(document, source)),
        outcome("C-10", check_status(document, source)),
        outcome("C-11", check_secrets(document)),
        outcome("C-12", check_control_characters(document)),
    ]
    return ConsistencyReport(checks=checks, passed_count=sum(1 for check in checks if check.passed), total_count=len(checks))


def consistency_text(report: ConsistencyReport) -> str:
    text = CONSISTENCY_LINE.format(passed=report.passed_count, total=report.total_count)
    failing = [check.id for check in report.checks if not check.passed]
    return text + FAILING_LINE.format(ids=", ".join(failing)) if failing else text


def with_consistency(document: ReportDocument, source: PipelineResult) -> ReportDocument:
    checked = document.model_copy(deep=True)
    report = check_document(checked, source)
    checked.meta.consistency = report
    method = section(checked, "method")
    if method is not None:
        for index, block in enumerate(method.blocks):
            if isinstance(block, SubheadingBlock) and block.text == HEADING_CONSISTENCY and index + 1 < len(method.blocks):
                following = method.blocks[index + 1]
                if isinstance(following, ParagraphBlock):
                    following.text = consistency_text(report)
                break
    return checked

