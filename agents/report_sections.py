from collections.abc import Callable, Iterable, Sequence

from agents.derived import BREADTH_CAP, CAPTION, MODERATE_AT, STRONG_AT, TYPE_ORDER, WEIGHTS, first_release, start_channel
from agents.mvp_agent import ASSUMED_PARTS, EFFORT_MONTHS, FOCUS_FACTOR, SCORE_WEIGHTS
from agents.notices import (
    STAGE_COMPETITOR,
    STAGE_EXTRACTION,
    STAGE_GTM,
    STAGE_MARKET,
    STAGE_MVP,
    STAGE_SEARCH,
    STAGE_SWOT,
    TITLES,
)
from models.report import (
    REPORT_SCHEMA_VERSION,
    BulletsBlock,
    CalloutBlock,
    FactPair,
    FactsBlock,
    MissingSection,
    ParagraphBlock,
    ReportBlock,
    ReportDocument,
    ReportItem,
    ReportMeta,
    ReportSection,
    SubheadingBlock,
    TableBlock,
)
from models.schemas import (
    Channel,
    LabeledItem,
    MvpFeature,
    PipelineResult,
    QuantEstimate,
    RiskItem,
    SearchBundle,
    StrategySourceKey,
)

SECTION_CATALOGUE = (
    ("cover", "Title block"),
    ("executive_summary", "Executive summary"),
    ("at_a_glance", "Validation at a glance"),
    ("idea", "The idea as understood"),
    ("market", "Market opportunity"),
    ("competitors", "Competitive landscape"),
    ("swot", "SWOT"),
    ("risks", "Risk assessment"),
    ("mvp", "MVP recommendation"),
    ("gtm", "Go-to-market strategy"),
    ("next_steps", "Recommended next steps"),
    ("method", "How this report was produced"),
    ("limitations", "Limitations"),
    ("sources", "Sources"),
)
APPENDIX_CATALOGUE = (
    ("appendix_run", "Appendix A: Run details"),
    ("appendix_glossary", "Appendix B: Terms"),
)
CATALOGUE_IDS = tuple(section_id for section_id, _ in (*SECTION_CATALOGUE, *APPENDIX_CATALOGUE))

REPORT_TITLE = "Startup validation report"
UNTITLED = "Untitled idea"
COVER_NOTE = "AI-assisted analysis; interpretations are labelled."
NOT_INCLUDED = "Not included: {reason}"
NOT_AVAILABLE = "Not available"
NOT_GIVEN = "Not given"
NOT_RECORDED = "Not recorded for this run"
ASSUMED = "assumed"
PARTIAL_LINE = "Some parts of this validation did not finish: {stages}."
NONE_FOUND = "None found in the evidence."
NONE_IN_RUN = "None found in this run."
NO_PRIORITY = "No priority segment could be chosen from the segments found."
NO_COMPARISON = "No feature comparison could be made."
NO_RISKS = "No risks were listed."
NO_FEATURES = "No features in this list."
NO_METRICS = "No success metrics were given."
NO_CHANNELS = "None were returned."
NO_NOTICES = "No quality notes for this run."
NO_SEARCHES = "No searches were recorded."
BROADER_NOTE = "Figures for a broader or different market. They are context only, not this idea's TAM, SAM or SOM."
OVER_CAPACITY = "The essential features need more effort than your team and time allow. Narrow the idea or allow more time."
COVERAGE_GAP_NOTE = "Not checked is not the same as safe."
CONSISTENCY_PENDING = "The consistency checks have not run yet."
HEADING_CONSISTENCY = "Consistency checks"
STANDING_ABSENCE = "Absence from search results does not prove absence."
STANDING_STRATEGY = "Strategy items are interpretations, not predictions."
PIPELINE_TEXT = (
    "The validation ran in stages. The idea was extracted from your description, the web was searched, and the "
    "market and the competitors were analysed from the search results. When strategy was included, a SWOT and risk "
    "review, an MVP recommendation and a go-to-market plan were written from those findings. This report compiles "
    "the stored results: it makes no new search and adds no new fact."
)

REASON_NO_SUMMARY = "No summary lines are stored with this result."
REASON_NOTHING_TO_COUNT = "No analysis finished, so there is nothing to count."
REASON_NO_IDEA = "The idea could not be extracted."
REASON_NOT_AVAILABLE = "This part is not available for this run."
REASON_NO_STRATEGY = "Strategy was not part of this validation."
REASON_NOTHING_TO_VERIFY = "No points to verify are stored with this result."

LABEL_RUN_STATUS = "Run status"
LABEL_PRIORITY_SEGMENT = "Priority segment"
LABEL_TARGET_SEGMENT = "Target segment"
LABEL_DIFFERENTIATOR = "Differentiator"
COLUMN_NUMBER = "#"
COLUMN_RISKS = "Addresses risks"
COLUMN_FEATURES = "Uses features"
TOTAL_KEY = "total"

BASIS_LABELS = {
    "sourced": "Sourced",
    "ai_interpretation": "AI interpretation",
    "user_provided": "From your idea",
    "assumption": "Assumption",
}
BASIS_MEANINGS = {
    "sourced": "Stated by a cited source.",
    "ai_interpretation": "The AI's reading of the evidence. No source states it.",
    "user_provided": "Taken from what you wrote.",
    "assumption": "Assumed where no evidence or input was available.",
}
RUN_STATUS_LABELS = {"complete": "Complete", "partial": "Partial", "failed": "Failed"}
FIGURE_STATUS_LABELS = {"sourced": "Sourced", "estimate_needs_verification": "Estimate", "unavailable": "Unavailable"}
CELL_LABELS = {
    "evidence_found": "+ Evidence found",
    "unclear": "? Unclear",
    "no_evidence_found": "\u2013 No evidence found in the sources",
}
TYPE_LABELS = {"direct": "Direct", "indirect": "Indirect", "emerging": "Emerging"}
LEVEL_WORDS = {"high": "High", "medium": "Medium", "low": "Low"}
LEVEL_MEANINGS = {
    "high": "Likely and harmful enough to address first.",
    "medium": "Worth a plan, but not the first thing to address.",
    "low": "Worth watching.",
}
EVIDENCE_LEVEL_WORDS = {"strong": "Strong", "limited": "Limited", "insufficient": "Insufficient"}
STRENGTH_LABELS = {"strong": "Strong", "moderate": "Moderate", "limited": "Limited"}
COMPONENT_LABELS = {"sourced_share": "sourced share", "source_breadth": "source breadth", "evidence_level": "evidence level"}
CATEGORY_LABELS = {
    "business": "Business",
    "market": "Market",
    "technical": "Technical",
    "financial": "Financial",
    "operational": "Operational",
}
SWOT_QUADRANTS = (
    ("strengths", "Strengths"),
    ("weaknesses", "Weaknesses"),
    ("opportunities", "Opportunities"),
    ("threats", "Threats"),
)
KIND_WORDS = {
    "digital": "Digital",
    "community": "Community",
    "partnership": "Partnership",
    "offline": "Offline",
    "direct_sales": "Direct sales",
    "product_led": "Product-led",
}
SPEED_WORDS = {"days": "Days", "weeks": "Weeks", "months": "Months"}
FIT_WORDS = {1: "Very weak", 2: "Weak", 3: "Moderate", 4: "Strong", 5: "Very strong"}
BUDGET_LABELS = {"bootstrapped": "Bootstrapped", "small": "Small budget", "funded": "Funded"}
SKILL_LABELS = {"non_technical": "Non-technical", "some": "Some technical", "strong": "Strong technical team"}
DIFFERENTIATOR_LABELS = {"hypothesis": "Hypothesis", "supported": "Supported"}
START_HERE = "Start here"
BUDGET_CONFLICT = "May be above a bootstrapped budget"
CONSTRAINT_LABELS = (
    ("team_size", "Team size"),
    ("months_to_mvp", "Months to the first release"),
    ("budget_level", "Budget"),
    ("technical_skill", "Technical skill"),
    ("launch_region", "Launch region"),
)
FIGURES = (("tam", "TAM"), ("sam", "SAM"), ("som", "SOM"))
STRATEGY_STAGES = (STAGE_SWOT, STAGE_MVP, STAGE_GTM)
STAGE_OUTPUTS = (
    (STAGE_EXTRACTION, "idea"),
    (STAGE_SEARCH, "search"),
    (STAGE_MARKET, "market"),
    (STAGE_COMPETITOR, "competitors"),
)
STRATEGY_OUTPUTS = ((STAGE_SWOT, "swot"), (STAGE_MVP, "mvp"), (STAGE_GTM, "gtm"))
SECTION_STAGES = {
    "idea": STAGE_EXTRACTION,
    "market": STAGE_MARKET,
    "competitors": STAGE_COMPETITOR,
    "swot": STAGE_SWOT,
    "risks": STAGE_SWOT,
    "mvp": STAGE_MVP,
    "gtm": STAGE_GTM,
}
NOTICE_GROUPS = (STAGE_EXTRACTION, STAGE_SEARCH, STAGE_MARKET, STAGE_COMPETITOR, STAGE_SWOT, STAGE_MVP, STAGE_GTM)
OTHER_NOTES = "Other notes"
EFFORT_MEANINGS = {"S": "small", "M": "medium", "L": "large"}
QUERY_SOURCES = (("search", "Main search"), ("market_search", "Market size"), ("competitor_search", "Competitors"))


def source_key(analysis: str, source_id: str) -> str:
    return f"{analysis}:{source_id.strip().upper()}"


def analysis_keys(analysis: str | None, source_ids: Iterable[str]) -> list[str]:
    if analysis is None:
        return []
    return list(dict.fromkeys(source_key(analysis, source_id) for source_id in source_ids if source_id.strip()))


def strategy_keys(sources: Iterable[StrategySourceKey]) -> list[str]:
    return list(dict.fromkeys(source_key(source.analysis, source.id) for source in sources))


def basis_of(value: object) -> str | None:
    return None if value is None else str(getattr(value, "value", value))


def number(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def joined(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def plain(value: str) -> str:
    text = value.replace("_", " ")
    return text[:1].upper() + text[1:]


def paragraph(text: str, basis: object = None, keys: Iterable[str] = ()) -> ParagraphBlock:
    return ParagraphBlock(text=text, basis=basis_of(basis), keys=list(keys))


def item(text: str, basis: object = None, keys: Iterable[str] = ()) -> ReportItem:
    return ReportItem(text=text, basis=basis_of(basis), keys=list(keys))


def facts(*pairs: tuple[str, str]) -> FactsBlock:
    return FactsBlock(pairs=[FactPair(label=label, value=value) for label, value in pairs])


def heading(text: str) -> SubheadingBlock:
    return SubheadingBlock(text=text)


def callout(kind: str, text: str) -> CalloutBlock:
    return CalloutBlock(kind=kind, text=text)


def table(caption: str, columns: list[str], rows: list[list[str]], keys: list[list[str]] | None = None,
          align: list[str] | None = None) -> TableBlock:
    return TableBlock(caption=caption, columns=columns, rows=rows, col_align=align or ["left"] * len(columns),
                      row_keys=keys or [[] for _ in rows])


def bullets(items: list[ReportItem], empty: str = NONE_FOUND) -> ReportBlock:
    return BulletsBlock(items=items) if items else paragraph(empty)


def labelled(items: Iterable[LabeledItem], analysis: str) -> list[ReportItem]:
    return [item(entry.text, entry.basis, analysis_keys(analysis, entry.source_ids)) for entry in items]


def distinct(texts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for text in texts:
        clean = " ".join(text.split())
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            kept.append(clean)
    return kept


def strategy_included(result: PipelineResult) -> bool:
    stages = {error.stage for error in result.errors} | {notice.stage for notice in result.notices}
    return any(getattr(result, field) is not None for _, field in STRATEGY_OUTPUTS) or bool(stages & set(STRATEGY_STAGES))


def unfinished_stages(result: PipelineResult) -> list[str]:
    failed = {error.stage for error in result.errors}
    if result.search is not None and result.search.queries_failed:
        failed.add(STAGE_SEARCH)
    outputs = [*STAGE_OUTPUTS, *(STRATEGY_OUTPUTS if strategy_included(result) else ())]
    return [stage for stage, field in outputs if getattr(result, field) is None or stage in failed]


def stage_names(stages: Iterable[str]) -> list[str]:
    return [TITLES.get(stage, stage) for stage in stages]


def stage_problem(result: PipelineResult, stage: str) -> str | None:
    error = next((entry for entry in result.errors if entry.stage == stage), None)
    if error is not None:
        return error.message
    notice = next((entry for entry in result.notices if entry.stage == stage and entry.severity != "info"), None)
    return notice.message if notice is not None else None


def missing_reason(section_id: str, result: PipelineResult) -> str | None:
    if section_id == "executive_summary":
        return None if result.executive_summary else REASON_NO_SUMMARY
    if section_id == "at_a_glance":
        has_content = result.market is not None or result.competitors is not None
        return None if has_content or any(getattr(result, f) for _, f in STRATEGY_OUTPUTS) else REASON_NOTHING_TO_COUNT
    if section_id == "next_steps":
        return None if result.verify_next else REASON_NOTHING_TO_VERIFY
    if section_id not in SECTION_STAGES:
        return None
    field = "swot" if section_id == "risks" else section_id
    if getattr(result, field) is not None:
        return None
    if section_id == "idea":
        return REASON_NO_IDEA
    stage = SECTION_STAGES[section_id]
    if stage in STRATEGY_STAGES and not strategy_included(result):
        return REASON_NO_STRATEGY
    return stage_problem(result, stage) or REASON_NOT_AVAILABLE


def strength_text(result: PipelineResult) -> str:
    strength = result.evidence_strength
    if strength is None:
        return NOT_AVAILABLE
    parts = [f"{COMPONENT_LABELS.get(part.key, part.key)} {number(part.value)}" for part in strength.components]
    return f"{STRENGTH_LABELS.get(strength.label, strength.label)} (score {number(strength.score)}; {', '.join(parts)})"


def figure_text(figure: QuantEstimate) -> str:
    word = FIGURE_STATUS_LABELS.get(figure.status, figure.status)
    return f"{word}: {figure.value}" if figure.value else word


def glance_facts(result: PipelineResult) -> list[FactPair]:
    market, competitors, swot, mvp, gtm = result.market, result.competitors, result.swot, result.mvp, result.gtm
    pairs = [("Evidence strength", strength_text(result))]
    for name, label in FIGURES:
        pairs.append((f"Market size ({label})", figure_text(getattr(market.market_size, name)) if market else NOT_AVAILABLE))
    if competitors is not None:
        counts = [sum(1 for entry in competitors.competitors if entry.type == kind) for kind in TYPE_ORDER]
        split = ", ".join(f"{count} {kind}" for kind, count in zip(TYPE_ORDER, counts))
        pairs.append(("Competitors found", f"{len(competitors.competitors)} ({split})"))
    else:
        pairs.append(("Competitors found", NOT_AVAILABLE))
    if swot is not None:
        split = ", ".join(f"{sum(1 for risk in swot.risks if risk.severity == level)} {level}" for level in LEVEL_WORDS)
        pairs.append(("Risks by severity", f"{len(swot.risks)} ({split})"))
    else:
        pairs.append(("Risks by severity", NOT_AVAILABLE))
    pairs.append(("MVP features in the first release", str(len(first_release(result))) if mvp is not None else NOT_AVAILABLE))
    channel = start_channel(result)
    pairs.append(("First recommended channel", channel.name if channel is not None else NOT_AVAILABLE if gtm is None else NOT_GIVEN))
    return [FactPair(label=label, value=value) for label, value in pairs]


def build_cover(result: PipelineResult, generated_at: str) -> list[ReportBlock]:
    idea = result.idea
    blocks: list[ReportBlock] = [
        facts(
            ("Idea", idea.idea_title if idea else UNTITLED),
            ("Industry", idea.industry if idea else NOT_AVAILABLE),
            ("Date", generated_at[:10]),
            (LABEL_RUN_STATUS, RUN_STATUS_LABELS[result.status]),
            ("Report version", str(REPORT_SCHEMA_VERSION)),
        ),
        callout("note", COVER_NOTE),
    ]
    unfinished = unfinished_stages(result)
    if unfinished:
        blocks.append(callout("warning", PARTIAL_LINE.format(stages=joined(stage_names(unfinished)))))
    return blocks


def build_executive_summary(result: PipelineResult) -> list[ReportBlock]:
    return [BulletsBlock(items=[
        item(line.text, line.basis, analysis_keys(line.analysis, line.source_ids)) for line in result.executive_summary
    ])]


def build_at_a_glance(result: PipelineResult) -> list[ReportBlock]:
    return [FactsBlock(pairs=glance_facts(result))]


def constraint_value(name: str, value: object) -> str:
    if name == "team_size":
        return "1 person" if value == 1 else f"{value} people"
    if name == "months_to_mvp":
        return "1 month" if value == 1 else f"{value} months"
    if name == "budget_level":
        return BUDGET_LABELS.get(str(value), plain(str(value)))
    if name == "technical_skill":
        return SKILL_LABELS.get(str(value), plain(str(value)))
    return str(value)


def resources(result: PipelineResult) -> list[tuple[str, str]]:
    given = result.constraints
    mvp = result.mvp
    assumed = set(mvp.quality.constraints_assumed) if mvp is not None else set()
    pairs = []
    for name, label in CONSTRAINT_LABELS:
        value = getattr(given, name) if given is not None else None
        if value is not None and name not in assumed:
            pairs.append((label, constraint_value(name, value)))
            continue
        used = getattr(mvp.constraints_used, name) if mvp is not None else None
        if used is not None and name in assumed:
            pairs.append((label, f"{constraint_value(name, used)} ({ASSUMED})"))
        else:
            pairs.append((label, NOT_GIVEN))
    return pairs


def build_idea(result: PipelineResult) -> list[ReportBlock]:
    idea = result.idea
    return [
        heading("Problem"),
        paragraph(idea.problem, "user_provided"),
        heading("Solution"),
        paragraph(idea.solution, "user_provided"),
        heading("Customers"),
        bullets([item(customer, "user_provided") for customer in idea.target_customers]),
        heading("Key features"),
        bullets([item(feature, "user_provided") for feature in idea.key_features]),
        heading("Resources"),
        facts(*resources(result)),
    ]


def figure_row(label: str, figure: QuantEstimate) -> list[str]:
    return [label, figure.value or NOT_AVAILABLE, FIGURE_STATUS_LABELS.get(figure.status, figure.status), figure.note or ""]


def build_market(result: PipelineResult) -> list[ReportBlock]:
    market = result.market
    analysis = "market"
    overview, demand = market.industry_overview, market.market_demand
    blocks: list[ReportBlock] = [
        heading("Industry overview"),
        paragraph(overview.summary, "ai_interpretation"),
        facts(("Market category", overview.market_category)),
    ]
    if overview.developments:
        blocks.append(BulletsBlock(items=labelled(overview.developments, analysis)))
    blocks += [heading("Demand"), paragraph(demand.summary, "ai_interpretation")]
    for title, entries in (("Demand evidence", demand.demand_evidence), ("Customer problems", demand.customer_problems),
                           ("Interest signals", demand.interest_signals)):
        blocks += [heading(title), bullets(labelled(entries, analysis))]
    figures = [getattr(market.market_size, name) for name, _ in FIGURES]
    blocks += [
        heading("Market size"),
        table("Market size for this idea", ["Figure", "Value", "Status", "Note"],
              [figure_row(label, figure) for (_, label), figure in zip(FIGURES, figures)],
              [analysis_keys(analysis, figure.source_ids) for figure in figures]),
    ]
    if market.broader_markets:
        blocks += [
            callout("note", BROADER_NOTE),
            table("Broader markets", ["Value", "Status", "Note"],
                  [figure_row("", figure)[1:] for figure in market.broader_markets],
                  [analysis_keys(analysis, figure.source_ids) for figure in market.broader_markets]),
        ]
    blocks += [heading("Trends"), bullets([
        item(f"{trend.trend} ({trend.category.capitalize()})", trend.basis, analysis_keys(analysis, trend.source_ids))
        for trend in market.trends
    ])]
    priority = market.priority_segment
    blocks += [
        heading("Segments"),
        table("Customer segments", ["Segment", "Description", "Segmented by", "Priority"], [
            [segment.name, segment.description, plain(segment.segmentation_basis),
             "Priority" if priority is not None and segment.name == priority.segment_name else ""]
            for segment in market.segments
        ], [analysis_keys(analysis, segment.source_ids) for segment in market.segments]),
    ]
    if priority is not None:
        segment = next((entry for entry in market.segments if entry.name == priority.segment_name), None)
        keys = analysis_keys(analysis, segment.source_ids) if segment is not None else []
        blocks += [facts((LABEL_PRIORITY_SEGMENT, priority.segment_name)), paragraph(priority.rationale, "ai_interpretation", keys)]
    else:
        blocks.append(callout("note", NO_PRIORITY))
    blocks += [
        heading("Opportunities"),
        bullets(labelled(market.opportunities, analysis)),
        heading("Limitations"),
        bullets(labelled(market.limitations, analysis)),
        heading("Evidence quality"),
        facts(("Evidence level", EVIDENCE_LEVEL_WORDS.get(market.data_quality.evidence_level, market.data_quality.evidence_level))),
    ]
    if market.data_quality.notes:
        blocks.append(BulletsBlock(items=[item(note) for note in market.data_quality.notes]))
    blocks += [callout("caveat", text) for text in distinct(market.caveats)]
    return blocks


def pricing_text(price: QuantEstimate) -> str:
    if not price.value:
        return NOT_AVAILABLE
    return f"{price.value} (Estimate)" if price.status == "estimate_needs_verification" else price.value


def build_competitors(result: PipelineResult) -> list[ReportBlock]:
    competitors = result.competitors
    analysis = "competitors"
    entries = competitors.competitors
    blocks: list[ReportBlock] = [
        heading("Competitors"),
        table("Competitors found", ["Competitor", "Type", "Offering", "Pricing as found"], [
            [entry.name, TYPE_LABELS.get(entry.type, entry.type), entry.offering or NOT_AVAILABLE, pricing_text(entry.pricing_model)]
            for entry in entries
        ], [analysis_keys(analysis, [*entry.source_ids, *entry.pricing_model.source_ids]) for entry in entries]),
        heading("Feature comparison"),
    ]
    comparison = competitors.comparison
    if comparison.features and comparison.rows:
        rows, keys = [], []
        for row in comparison.rows:
            cells = {cell.feature: cell for cell in row.cells}
            rows.append([row.competitor, *(CELL_LABELS.get(cells[f].status, cells[f].status) if f in cells else NOT_AVAILABLE
                                           for f in comparison.features)])
            keys.append(analysis_keys(analysis, [source for cell in row.cells for source in cell.source_ids]))
        blocks.append(table("Feature comparison", ["Competitor", *comparison.features], rows, keys))
    else:
        blocks.append(paragraph(NO_COMPARISON))
    if comparison.feature_coverage:
        blocks.append(table("Feature coverage", ["Feature", "Competitors with evidence"],
                            [[entry.feature, str(entry.competitors_with_evidence)] for entry in comparison.feature_coverage],
                            align=["left", "right"]))
    gaps = competitors.market_gaps
    blocks += [heading("Possible gaps"), bullets([
        item(f"{gap.description} ({gap.confidence} confidence, a hypothesis)", gap.basis, analysis_keys(analysis, gap.source_ids))
        for gap in gaps
    ])]
    blocks += [callout("caveat", text) for text in distinct([*(gap.caveat for gap in gaps), *competitors.caveats])]
    blocks += [
        heading("Differentiation opportunities"),
        bullets(labelled(competitors.differentiation_opportunities, analysis)),
        heading("Evidence quality"),
        facts(("Evidence level", EVIDENCE_LEVEL_WORDS.get(competitors.data_quality.evidence_level,
                                                          competitors.data_quality.evidence_level))),
    ]
    if competitors.data_quality.notes:
        blocks.append(BulletsBlock(items=[item(note) for note in competitors.data_quality.notes]))
    return blocks


def build_swot(result: PipelineResult) -> list[ReportBlock]:
    swot = result.swot
    blocks: list[ReportBlock] = [paragraph(swot.summary, "ai_interpretation")] if swot.summary else []
    for field, label in SWOT_QUADRANTS:
        entries = getattr(swot, field)
        blocks += [heading(label), bullets([
            item(f"{entry.text} Why it matters: {entry.why_it_matters}" if entry.why_it_matters else entry.text,
                 entry.basis, strategy_keys(entry.sources))
            for entry in entries
        ], NONE_IN_RUN)]
    return blocks


def risk_numbers(result: PipelineResult) -> dict[str, str]:
    risks = result.swot.risks if result.swot is not None else []
    return {risk.id: str(index) for index, risk in enumerate(risks, start=1)}


def feature_numbers(result: PipelineResult) -> dict[str, str]:
    features = result.mvp.features if result.mvp is not None else []
    return {feature.id: str(feature.rank) for feature in features}


def references(ids: Sequence[str], numbers: dict[str, str]) -> str:
    return ", ".join(numbers.get(value, value) for value in ids) if ids else "None"


def risk_row(index: int, risk: RiskItem) -> list[str]:
    return [str(index), CATEGORY_LABELS.get(risk.category, plain(risk.category)), risk.title,
            LEVEL_WORDS[risk.likelihood], LEVEL_WORDS[risk.impact], LEVEL_WORDS[risk.severity], risk.mitigation,
            risk.early_warning_signal, BASIS_LABELS[risk.basis]]


def build_risks(result: PipelineResult) -> list[ReportBlock]:
    swot = result.swot
    blocks: list[ReportBlock] = []
    if swot.risks:
        blocks.append(table("Risk register", [COLUMN_NUMBER, "Category", "Risk", "Likelihood", "Impact", "Severity", "Mitigation",
                                              "Early warning sign", "Basis"],
                            [risk_row(index, risk) for index, risk in enumerate(swot.risks, start=1)],
                            [strategy_keys(risk.sources) for risk in swot.risks],
                            ["right", *["left"] * 8]))
    else:
        blocks.append(paragraph(NO_RISKS))
    covered = [f"{CATEGORY_LABELS.get(name, plain(name))} {count}" for name, count in swot.risk_category_coverage.items()]
    if covered:
        blocks.append(paragraph(f"Risks by category: {', '.join(covered)}."))
    if swot.coverage_gaps:
        missing = joined([CATEGORY_LABELS.get(name, plain(name)).lower() for name in swot.coverage_gaps])
        blocks.append(callout("note", f"No {missing} risk was found in this run. {COVERAGE_GAP_NOTE}"))
    return blocks


def feature_table(caption: str, features: list[MvpFeature], risks: dict[str, str]) -> ReportBlock:
    if not features:
        return paragraph(NO_FEATURES)
    return table(caption, [COLUMN_NUMBER, "Feature", "Need", "Differentiation", "Feasibility", "Effort", "Score", COLUMN_RISKS, "Basis"], [
        [str(feature.rank), feature.name, str(feature.customer_need), str(feature.differentiation), str(feature.feasibility),
         feature.effort, number(feature.score), references(feature.mitigates_risk_ids, risks), BASIS_LABELS[feature.basis]]
        for feature in features
    ], [strategy_keys(feature.sources) for feature in features], ["right", "left", "right", "right", "right", "left", "right",
                                                                  "left", "left"])


def ranking_text() -> list[ReportBlock]:
    return [
        heading("How the ranking works"),
        paragraph(
            "Each feature is rated from 1 to 5 by the AI for need, differentiation and feasibility. Score = "
            f"{SCORE_WEIGHTS['customer_need']} \u00d7 need + {SCORE_WEIGHTS['differentiation']} \u00d7 differentiation + "
            f"{SCORE_WEIGHTS['feasibility']} \u00d7 feasibility."
        ),
        paragraph("Features essential to the idea come first, then higher scores, then lower effort."),
        paragraph(
            f"Effort in person-months, an AI estimate: S is {number(EFFORT_MONTHS['S'])}, M is {number(EFFORT_MONTHS['M'])}, "
            f"L is {number(EFFORT_MONTHS['L'])}."
        ),
        paragraph(
            f"Capacity = team size \u00d7 months \u00d7 {FOCUS_FACTOR}, for the time a team can give to building. Features join "
            "the first release in rank order while they fit."
        ),
        paragraph("These weights are planning rules of thumb, not facts about your market."),
    ]


def build_mvp(result: PipelineResult) -> list[ReportBlock]:
    mvp = result.mvp
    risks = risk_numbers(result)
    ranked = sorted(mvp.features, key=lambda feature: feature.rank)
    first = [feature for feature in ranked if feature.tier == "mvp"]
    later = [feature for feature in ranked if feature.tier != "mvp"]
    used = mvp.constraints_used
    blocks: list[ReportBlock] = [paragraph(mvp.summary, "ai_interpretation")] if mvp.summary else []
    blocks.append(facts(
        ("Capacity", f"Planned {number(mvp.planned_person_months)} of {number(mvp.capacity_person_months)} person-months"),
        ("Team size", constraint_value("team_size", used.team_size) if used.team_size is not None else NOT_GIVEN),
        ("Months to the first release",
         constraint_value("months_to_mvp", used.months_to_mvp) if used.months_to_mvp is not None else NOT_GIVEN),
    ))
    if mvp.over_capacity:
        blocks.append(callout("warning", OVER_CAPACITY))
    blocks += [heading("In the first release"), feature_table("First release", first, risks),
               heading("Later"), feature_table("Later", later, risks)]
    names = {feature.id: feature.name for feature in mvp.features}
    reasons = [item(f"{names.get(key, key)}: {reason}") for key, reason in mvp.deferred_reasons.items()]
    if reasons:
        blocks += [heading("Why some features wait"), BulletsBlock(items=reasons)]
    assumed = [name for name in mvp.quality.constraints_assumed if name in ASSUMED_PARTS]
    if assumed:
        values = joined([ASSUMED_PARTS[name].format(value=getattr(used, name)) for name in assumed])
        blocks += [heading("Assumptions"), paragraph(f"The plan assumes {values} because they were not given.", "assumption")]
    blocks += [heading("Success metrics")]
    if mvp.success_metrics:
        blocks.append(table("Success metrics", ["Metric", "How to measure", "Suggested target", "Basis"], [
            [metric.name, metric.how_to_measure, metric.suggested_target or NOT_GIVEN, BASIS_LABELS[metric.basis]]
            for metric in mvp.success_metrics
        ]))
    else:
        blocks.append(paragraph(NO_METRICS))
    return blocks + ranking_text()


def channel_name(channel: Channel) -> str:
    marks = [START_HERE] if channel.start_here else []
    if channel.budget_conflict:
        marks.append(BUDGET_CONFLICT)
    return f"{channel.name} ({'; '.join(marks)})" if marks else channel.name


def build_gtm(result: PipelineResult) -> list[ReportBlock]:
    gtm = result.gtm
    risks, features = risk_numbers(result), feature_numbers(result)
    position = gtm.positioning
    blocks: list[ReportBlock] = [paragraph(gtm.summary, "ai_interpretation")] if gtm.summary else []
    blocks += [
        heading("Positioning"),
        paragraph(position.statement, position.basis, strategy_keys(position.sources)),
        facts(
            (LABEL_TARGET_SEGMENT, position.target_segment),
            ("For whom", position.for_whom),
            ("Problem", position.problem),
            ("Category", position.category),
            ("Key benefit", position.key_benefit),
            ("Alternative", position.alternative),
            (LABEL_DIFFERENTIATOR, f"{position.differentiator} ({DIFFERENTIATOR_LABELS[position.differentiator_status]})"),
        ),
        heading("Channels"),
    ]
    channels = sorted(gtm.channels, key=lambda channel: channel.priority)
    if channels:
        blocks.append(table("Channels, in the order to try them", [
            "Priority", "Channel", "Kind", "Cost", "Speed", "Audience fit", "First experiment", "Success signal",
            COLUMN_FEATURES, COLUMN_RISKS, "Basis",
        ], [
            [str(channel.priority), channel_name(channel), KIND_WORDS.get(channel.kind, plain(channel.kind)),
             LEVEL_WORDS[channel.cost_level], SPEED_WORDS[channel.speed_to_first_result],
             f"{FIT_WORDS[channel.audience_fit]}, {channel.audience_fit} of 5", channel.first_experiment, channel.success_signal,
             references(channel.uses_feature_ids, features), references(channel.addresses_risk_ids, risks),
             BASIS_LABELS[channel.basis]]
            for channel in channels
        ], [strategy_keys(channel.sources) for channel in channels], ["right", *["left"] * 10]))
    else:
        blocks.append(paragraph(NO_CHANNELS))
    blocks += [heading("Early customers"), bullets([
        item(f"{tactic.tactic} Where to find them: {tactic.where_to_find_them}. Offer: {tactic.offer}. "
             f"How to measure: {tactic.how_to_measure}", tactic.basis, strategy_keys(tactic.sources))
        for tactic in gtm.early_customers
    ], NO_CHANNELS)]
    blocks.append(heading("Launch phases"))
    for phase in gtm.launch_phases:
        blocks += [heading(phase.name), paragraph(f"Goal: {phase.goal}", "ai_interpretation")]
        if phase.actions:
            blocks.append(BulletsBlock(items=[item(action, "ai_interpretation") for action in phase.actions]))
    if not gtm.launch_phases:
        blocks.append(paragraph(NO_CHANNELS))
    blocks.append(heading("Key messages"))
    if gtm.key_messages:
        blocks.append(table("Key messages", ["Audience", "Message", "Proof needed"], [
            [message.audience, message.message, message.proof_needed or NOT_GIVEN] for message in gtm.key_messages
        ]))
    else:
        blocks.append(paragraph(NO_CHANNELS))
    return blocks


def build_next_steps(result: PipelineResult) -> list[ReportBlock]:
    return [heading("What to verify"), BulletsBlock(items=[
        item(entry.text, None, analysis_keys(entry.analysis, entry.source_ids)) for entry in result.verify_next
    ])]


def usage_pairs(result: PipelineResult) -> list[tuple[str, str]]:
    usage = result.usage
    if usage is None:
        return [("AI requests", NOT_RECORDED), ("Web searches", NOT_RECORDED)]
    return [("AI requests", str(usage.llm_calls)), ("Web searches", str(usage.search_calls))]


def notice_blocks(result: PipelineResult) -> list[ReportBlock]:
    if not result.notices:
        return [paragraph(NO_NOTICES)]
    blocks: list[ReportBlock] = []
    groups = [*NOTICE_GROUPS, None]
    for stage in groups:
        notes = [notice for notice in result.notices if (notice.stage if notice.stage in NOTICE_GROUPS else None) == stage]
        if notes:
            blocks += [heading(TITLES[stage] if stage else OTHER_NOTES),
                       BulletsBlock(items=[item(text) for text in distinct(notice.message for notice in notes)])]
    return blocks


def build_method(result: PipelineResult) -> list[ReportBlock]:
    pairs = [(LABEL_RUN_STATUS, RUN_STATUS_LABELS[result.status])]
    unfinished = unfinished_stages(result)
    if unfinished:
        pairs.append(("Stages that did not finish", joined(stage_names(unfinished))))
    weights = ", ".join(f"{COMPONENT_LABELS[key]} {number(value)}" for key, value in WEIGHTS.items())
    return [
        paragraph(PIPELINE_TEXT),
        facts(*pairs),
        heading("Basis labels"),
        facts(*((BASIS_LABELS[key], BASIS_MEANINGS[key]) for key in BASIS_LABELS)),
        heading("Evidence strength"),
        paragraph(
            f"Evidence strength combines three parts with these weights: {weights}. Source breadth counts distinct "
            f"source websites up to {BREADTH_CAP}. It is Strong at {number(STRONG_AT)} or above, Moderate from "
            f"{number(MODERATE_AT)} and Limited below. {CAPTION}"
        ),
        heading(HEADING_CONSISTENCY),
        paragraph(CONSISTENCY_PENDING),
        heading("AI requests and searches"),
        facts(*usage_pairs(result)),
        heading("Quality notes"),
        *notice_blocks(result),
    ]


def limitation_texts(result: PipelineResult) -> list[str]:
    texts: list[str] = []
    for analysis in (result.market, result.competitors):
        if analysis is not None:
            texts += [*analysis.data_quality.notes, *analysis.caveats]
    for strategy in (result.swot, result.mvp, result.gtm):
        if strategy is not None:
            texts += strategy.limitations
    texts += [notice.message for notice in result.notices if notice.severity in ("warning", "error")]
    return texts


def build_limitations(result: PipelineResult) -> list[ReportBlock]:
    market_items = labelled(result.market.limitations, "market") if result.market is not None else []
    seen = {" ".join(entry.text.split()).lower() for entry in market_items}
    plain_items = [item(text) for text in distinct(limitation_texts(result)) if text.lower() not in seen]
    blocks: list[ReportBlock] = [bullets([*market_items, *plain_items], NONE_IN_RUN)]
    return blocks + [heading("Standing statements"),
                     BulletsBlock(items=[item(STANDING_ABSENCE), item(STANDING_STRATEGY)])]


def build_sources(result: PipelineResult) -> list[ReportBlock]:
    return []


def stage_label(key: str) -> str:
    return TITLES.get(key, plain(key))


def query_rows(result: PipelineResult) -> list[list[str]]:
    rows = []
    for field, label in QUERY_SOURCES:
        bundle: SearchBundle | None = getattr(result, field)
        for section in bundle.sections if bundle is not None else []:
            rows.append([label, section.query])
    return rows


def build_appendix_run(result: PipelineResult) -> list[ReportBlock]:
    usage = result.usage
    rows = []
    for key, seconds in result.timings.items():
        if key == TOTAL_KEY:
            continue
        entry = usage.by_stage.get(key) if usage is not None else None
        rows.append([stage_label(key), number(seconds), str(entry.llm_calls) if entry else NOT_AVAILABLE,
                     str(entry.search_calls) if entry else NOT_AVAILABLE])
    if TOTAL_KEY in result.timings:
        rows.append(["Total", number(result.timings[TOTAL_KEY]), str(usage.llm_calls) if usage else NOT_AVAILABLE,
                     str(usage.search_calls) if usage else NOT_AVAILABLE])
    blocks: list[ReportBlock] = [
        heading("Stage timings"),
        table("Stage timings", ["Stage", "Seconds", "AI requests", "Searches"], rows, align=["left", "right", "right", "right"]),
        facts(*usage_pairs(result)),
        heading("Searches run"),
    ]
    queries = query_rows(result)
    blocks.append(table("Search queries", ["Search", "Query"], queries) if queries else paragraph(NO_SEARCHES))
    blocks.append(heading("Versions"))
    versions = result.versions
    if versions is None:
        blocks.append(facts(("Versions", NOT_RECORDED)))
    else:
        blocks.append(facts(
            ("Query profile", versions.query_profile),
            ("Prompt profile", versions.prompt_profile),
            *((f"Prompt version ({agent})", version) for agent, version in versions.prompt_versions.items()),
            ("App version", versions.app_version),
        ))
    return blocks


def build_appendix_glossary(result: PipelineResult) -> list[ReportBlock]:
    return [
        heading("Basis labels"),
        facts(*((BASIS_LABELS[key], BASIS_MEANINGS[key]) for key in BASIS_LABELS)),
        heading("Severity levels"),
        facts(*((LEVEL_WORDS[key], LEVEL_MEANINGS[key]) for key in LEVEL_WORDS)),
        heading("Effort sizes"),
        facts(*((size, f"A {EFFORT_MEANINGS[size]} feature, about {number(months)} person-months (an AI estimate).")
                for size, months in EFFORT_MONTHS.items())),
        heading("Evidence strength levels"),
        facts(
            (STRENGTH_LABELS["strong"], f"A score of {number(STRONG_AT)} or above."),
            (STRENGTH_LABELS["moderate"], f"A score from {number(MODERATE_AT)} to below {number(STRONG_AT)}."),
            (STRENGTH_LABELS["limited"], f"A score below {number(MODERATE_AT)}."),
        ),
    ]


BUILDERS: dict[str, Callable[[PipelineResult], list[ReportBlock]]] = {
    "executive_summary": build_executive_summary,
    "at_a_glance": build_at_a_glance,
    "idea": build_idea,
    "market": build_market,
    "competitors": build_competitors,
    "swot": build_swot,
    "risks": build_risks,
    "mvp": build_mvp,
    "gtm": build_gtm,
    "next_steps": build_next_steps,
    "method": build_method,
    "limitations": build_limitations,
    "sources": build_sources,
    "appendix_run": build_appendix_run,
    "appendix_glossary": build_appendix_glossary,
}


def not_included(reason: str) -> list[ReportBlock]:
    return [callout("note", NOT_INCLUDED.format(reason=reason))]


def build_section(section_id: str, title: str, result: PipelineResult, generated_at: str) -> tuple[ReportSection, str | None]:
    reason = missing_reason(section_id, result)
    if reason is not None:
        return ReportSection(id=section_id, title=title, blocks=not_included(reason)), reason
    blocks = build_cover(result, generated_at) if section_id == "cover" else BUILDERS[section_id](result)
    return ReportSection(id=section_id, title=title, blocks=blocks), None


def default_app_version() -> str:
    from routes.meta_routes import APP_VERSION

    return APP_VERSION


def build_document(
    result: PipelineResult,
    *,
    run_id: str,
    generated_at: str,
    source_fingerprint: str = "",
    narrative_status: str = "skipped",
    prompt_version: str | None = None,
    app_version: str | None = None,
) -> ReportDocument:
    built = {}
    missing: list[MissingSection] = []
    for section_id, title in (*SECTION_CATALOGUE, *APPENDIX_CATALOGUE):
        section, reason = build_section(section_id, title, result, generated_at)
        built[section_id] = section
        if reason is not None:
            missing.append(MissingSection(id=section_id, reason=reason))
    missing_ids = {entry.id for entry in missing}
    idea = result.idea
    return ReportDocument(
        title=REPORT_TITLE,
        subtitle=idea.idea_title if idea else UNTITLED,
        meta=ReportMeta(
            run_id=run_id,
            generated_at=generated_at,
            source_fingerprint=source_fingerprint,
            run_status=result.status,
            idea_title=idea.idea_title if idea else UNTITLED,
            industry=idea.industry if idea else NOT_AVAILABLE,
            sections_included=[section_id for section_id in CATALOGUE_IDS if section_id not in missing_ids],
            sections_missing=missing,
            narrative_status=narrative_status,
            prompt_version=prompt_version,
            app_version=app_version if app_version is not None else default_app_version(),
        ),
        sections=[built[section_id] for section_id, _ in SECTION_CATALOGUE],
        appendix_sections=[built[section_id] for section_id, _ in APPENDIX_CATALOGUE],
    )
