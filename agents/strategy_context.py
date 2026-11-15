import re
from collections.abc import Iterable
from dataclasses import dataclass

from agents.evidence import _tag_pattern, clean_prompt_text
from config import get_settings
from models.schemas import (
    ANALYSES,
    CONSTRAINT_FIELDS,
    CompetitorAnalysisResult,
    ExtractedIdea,
    LabeledItem,
    MarketFigure,
    MarketOpportunityResult,
    MvpResult,
    QuantEstimate,
    SourceRef,
    StrategyConstraints,
    StrategySourceKey,
    SwotRiskResult,
)

MARKET, COMPETITORS = ANALYSES
IDEA_PREFIX = "IDEA"
CONSTRAINT_PREFIX = "CON"
MARKET_PREFIX = "MKT"
COMPETITOR_PREFIX = "CMP"
RISK_PREFIX = "RSK"
FEATURE_PREFIX = "MVP"
REF_PREFIXES = (IDEA_PREFIX, CONSTRAINT_PREFIX, MARKET_PREFIX, COMPETITOR_PREFIX, RISK_PREFIX, FEATURE_PREFIX)

DIGEST_TAGS = ("facts",)
DIGEST_OPEN = "<facts>"
DIGEST_CLOSE = "</facts>"

SOURCED = "sourced"
INTERPRETATION = "ai_interpretation"
ASSUMPTION = "assumption"
USER_PROVIDED = "user_provided"

CONSTRAINT_DEFAULTS = {"team_size": 2, "months_to_mvp": 3}
CONSTRAINT_LABELS = {
    "team_size": "Team size",
    "months_to_mvp": "Time to first release",
    "budget_level": "Budget level",
    "technical_skill": "Technical skill",
    "launch_region": "Launch region",
}
CONSTRAINT_UNITS = {"team_size": ("person", "people"), "months_to_mvp": ("month", "months")}
CONSTRAINT_VALUES = {
    "bootstrapped": "bootstrapped",
    "small": "small budget",
    "funded": "funded",
    "non_technical": "non-technical",
    "some": "some technical skill",
    "strong": "strong technical team",
}
STATED = "stated by the founder"
ASSUMED = "an assumed default because the founder did not give one"

FIGURE_LABELS = (("tam", "TAM"), ("sam", "SAM"), ("som", "SOM"))
FIGURE_STATUSES = {
    "sourced": "stated by a source",
    "estimate_needs_verification": "an estimate that needs verification",
    "unavailable": "not available",
}

TRENDS_KEPT = 3
DEMAND_KEPT = 3
TRIM_ORDER = (("broader_market", 0), ("trend", TRENDS_KEPT), ("query_used", 0), ("demand", DEMAND_KEPT))

_DIGEST_TAG_PATTERN = _tag_pattern(DIGEST_TAGS)
_STORED_ID = re.compile(r"[A-Z]+(\d+)")
_ID_LIST = r"S\d+(?:\s*(?:,|and|&)\s*S\d+)*"
_CITED_IDS = re.compile(rf"\s*\(\s*(?:sources?\s+)?{_ID_LIST}\s*\)", re.IGNORECASE)
_NAMED_IDS = re.compile(rf"\b(sources?)\s+{_ID_LIST}\b", re.IGNORECASE)


@dataclass(frozen=True)
class Fact:
    ref: str
    kind: str
    text: str
    basis: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Digest:
    facts: tuple[Fact, ...]
    text: str
    max_chars: int
    dropped: tuple[str, ...] = ()

    @property
    def fits(self) -> bool:
        return len(self.text) <= self.max_chars

    @property
    def refs(self) -> frozenset[str]:
        return frozenset(fact.ref for fact in self.facts)

    def fact(self, ref: str) -> Fact | None:
        wanted = normalize_ref(ref)
        return next((fact for fact in self.facts if fact.ref == wanted), None)


def normalize_ref(ref: object) -> str:
    return "".join(str(ref or "").split()).strip("[]").upper()


def ref_prefix(ref: str) -> str:
    return normalize_ref(ref).split(".", 1)[0]


def source_key(analysis: str, source_id: str) -> str:
    return f"{analysis}:{source_id}"


def to_source_key(key: str) -> StrategySourceKey:
    analysis, source_id = key.split(":", 1)
    return StrategySourceKey(analysis=analysis, id=source_id)


def clean_fact_text(text: object) -> str:
    previous, cleaned = None, clean_prompt_text(str(text or ""))
    while cleaned != previous:
        previous, cleaned = cleaned, clean_prompt_text(_DIGEST_TAG_PATTERN.sub("", cleaned))
    return cleaned


def apply_constraint_defaults(
    constraints: StrategyConstraints | None,
) -> tuple[StrategyConstraints, list[str], list[str]]:
    given = constraints or StrategyConstraints()
    provided = [name for name in CONSTRAINT_FIELDS if getattr(given, name) is not None]
    assumed = [name for name in CONSTRAINT_DEFAULTS if getattr(given, name) is None]
    used = given.model_copy(update={name: CONSTRAINT_DEFAULTS[name] for name in assumed})
    return used, provided, assumed


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text.endswith((".", "!", "?")) else f"{text}."


def _joined(*parts: str | None) -> str:
    return " ".join(_sentence(clean_fact_text(part)) for part in parts if part and clean_fact_text(part))


def _listed(label: str, values: Iterable[str]) -> str | None:
    cleaned = [clean_fact_text(value) for value in values]
    cleaned = [value for value in cleaned if value]
    return f"{label}: {'; '.join(cleaned)}" if cleaned else None


def _known_ids(sources: list[SourceRef]) -> frozenset[str]:
    return frozenset(source.id.strip().upper() for source in sources)


def _keys(analysis: str, source_ids: Iterable[str], known: frozenset[str]) -> tuple[str, ...]:
    keys: list[str] = []
    for source_id in source_ids:
        normalized = str(source_id).strip().upper()
        key = source_key(analysis, normalized)
        if normalized in known and key not in keys:
            keys.append(key)
    return tuple(keys)


def _derived_basis(keys: tuple[str, ...]) -> str:
    return SOURCED if keys else INTERPRETATION


def _figure_basis(figure: QuantEstimate, keys: tuple[str, ...]) -> str:
    return SOURCED if figure.status == SOURCED and keys else INTERPRETATION


def _figure_text(label: str, figure: QuantEstimate) -> str:
    status = FIGURE_STATUSES.get(figure.status, figure.status)
    value = clean_fact_text(figure.value)
    head = f"{label}: {value} ({status})" if value else f"{label}: no reliable figure was found"
    return _joined(head, f"Note: {figure.note}" if figure.note else None)


Entry = tuple[str, str, str, tuple[str, ...]]


def _entry(kind: str, text: str, basis: str, sources: tuple[str, ...] = ()) -> Entry | None:
    return (kind, text, basis, sources) if text else None


def _labeled(kind: str, label: str, item: LabeledItem, analysis: str, known: frozenset[str]) -> Entry | None:
    return _entry(kind, _joined(f"{label}: {item.text}"), _value(item.basis), _keys(analysis, item.source_ids, known))


def _idea_entries(idea: ExtractedIdea | None) -> list[Entry | None]:
    if idea is None:
        return []
    entries = [
        _entry("idea_title", _joined(f"Idea: {idea.idea_title}"), USER_PROVIDED),
        _entry("idea_problem", _joined(f"Problem: {idea.problem}"), USER_PROVIDED),
        _entry("idea_solution", _joined(f"Solution: {idea.solution}"), USER_PROVIDED),
    ]
    entries += [_entry("idea_customer", _joined(f"Target customer: {value}"), USER_PROVIDED) for value in idea.target_customers]
    entries.append(_entry("idea_industry", _joined(f"Industry: {idea.industry}"), USER_PROVIDED))
    entries += [_entry("key_feature", _joined(f"Founder-listed feature: {value}"), USER_PROVIDED) for value in idea.key_features]
    return entries


def _constraint_value(name: str, value: object) -> str:
    if name in CONSTRAINT_UNITS:
        one, many = CONSTRAINT_UNITS[name]
        return f"{value} {one if value == 1 else many}"
    return CONSTRAINT_VALUES.get(str(value), str(value))


def _constraint_entries(constraints: StrategyConstraints | None) -> list[Entry | None]:
    used, provided, assumed = apply_constraint_defaults(constraints)
    entries: list[Entry | None] = []
    for name in CONSTRAINT_FIELDS:
        value = getattr(used, name)
        if value is None:
            continue
        how, basis = (ASSUMED, ASSUMPTION) if name in assumed else (STATED, USER_PROVIDED)
        text = _joined(f"{CONSTRAINT_LABELS[name]}: {_constraint_value(name, value)}, {how}")
        entries.append(_entry("constraint", text, basis))
    return entries


def _market_entries(market: MarketOpportunityResult | None) -> list[Entry | None]:
    if market is None:
        return []
    known = _known_ids(market.sources)
    overview, demand = market.industry_overview, market.market_demand
    entries = [
        _entry("industry", _joined(f"Industry overview: {overview.summary}"), INTERPRETATION),
        _entry("industry", _joined(f"Market category: {overview.market_category}"), INTERPRETATION),
    ]
    entries += [_labeled("industry_development", "Industry development", item, MARKET, known) for item in overview.developments]
    entries.append(_entry("demand_summary", _joined(f"Demand overview: {demand.summary}"), INTERPRETATION))
    for label, items in (
        ("Demand evidence", demand.demand_evidence),
        ("Customer problem", demand.customer_problems),
        ("Interest signal", demand.interest_signals),
    ):
        entries += [_labeled("demand", label, item, MARKET, known) for item in items]
    for name, label in FIGURE_LABELS:
        figure: MarketFigure = getattr(market.market_size, name)
        keys = _keys(MARKET, figure.source_ids, known)
        entries.append(_entry("market_size", _figure_text(f"{label} for this idea's own market", figure), _figure_basis(figure, keys), keys))
    for figure in market.broader_markets:
        keys = _keys(MARKET, figure.source_ids, known)
        text = _figure_text("Broader market figure, not this idea's own market", figure)
        entries.append(_entry("broader_market", text, _figure_basis(figure, keys), keys))
    for trend in market.trends:
        text = _joined(f"Trend ({trend.category}): {trend.trend}")
        entries.append(_entry("trend", text, _value(trend.basis), _keys(MARKET, trend.source_ids, known)))
    for segment in market.segments:
        keys = _keys(MARKET, segment.source_ids, known)
        text = _joined(f"Customer segment: {segment.name}", segment.description, _listed("Needs", segment.needs))
        entries.append(_entry("segment", text, _derived_basis(keys), keys))
        entries += [_labeled("pain_point", f"Pain point of {segment.name}", item, MARKET, known) for item in segment.pain_points]
    priority = market.priority_segment
    if priority is not None:
        text = _joined(f"Priority segment: {priority.segment_name}", f"Why: {priority.rationale}", _listed("Risks", priority.risks))
        entries.append(_entry("priority_segment", text, INTERPRETATION))
    entries += [_labeled("opportunity", "Market opportunity", item, MARKET, known) for item in market.opportunities]
    entries += [_labeled("limitation", "Market analysis limitation", item, MARKET, known) for item in market.limitations]
    quality = market.data_quality
    entries.append(_entry("data_quality", _joined(f"Market evidence level: {quality.evidence_level}", *quality.notes), INTERPRETATION))
    entries += [_entry("caveat", _joined(caveat), INTERPRETATION) for caveat in market.caveats]
    return entries


def _competitor_entries(competitors: CompetitorAnalysisResult | None) -> list[Entry | None]:
    if competitors is None:
        return []
    known = _known_ids(competitors.sources)
    entries: list[Entry | None] = []
    for competitor in competitors.competitors:
        name = clean_fact_text(competitor.name)
        keys = _keys(COMPETITORS, competitor.source_ids, known)
        text = _joined(
            f"Competitor: {name} ({competitor.type} competitor)",
            competitor.relevance_note,
            f"Offering: {competitor.offering}" if competitor.offering else None,
            f"Target segment: {competitor.target_segment}" if competitor.target_segment else None,
            f"Value proposition: {competitor.value_proposition}" if competitor.value_proposition else None,
            f"Positioning: {competitor.positioning}" if competitor.positioning else None,
            f"Compared with this idea: {competitor.differentiation_vs_startup}" if competitor.differentiation_vs_startup else None,
        )
        entries.append(_entry("competitor", text, competitor.basis, keys))
        features = _listed(f"Features of {name}", competitor.key_features)
        if features:
            entries.append(_entry("competitor_feature", _joined(features), competitor.basis, keys))
        pricing = competitor.pricing_model
        price_keys = _keys(COMPETITORS, pricing.source_ids, known)
        entries.append(_entry("pricing", _figure_text(f"Pricing of {name}", pricing), _figure_basis(pricing, price_keys), price_keys))
        entries += [_labeled("competitor_strength", f"Strength of {name}", item, COMPETITORS, known) for item in competitor.strengths]
        entries += [_labeled("competitor_weakness", f"Weakness of {name}", item, COMPETITORS, known) for item in competitor.weaknesses]
    comparison = competitors.comparison
    for coverage in comparison.feature_coverage:
        cells = [cell for row in comparison.rows for cell in row.cells if cell.feature == coverage.feature and cell.status == "evidence_found"]
        keys = _keys(COMPETITORS, [source_id for cell in cells for source_id in cell.source_ids], known)
        text = _joined(
            f"Feature compared: {coverage.feature}",
            f"Evidence found for {coverage.competitors_with_evidence} of {len(comparison.rows)} competitors compared",
        )
        entries.append(_entry("coverage", text, _derived_basis(keys), keys))
    for gap in competitors.market_gaps:
        text = _joined(
            f"Possible market gap ({gap.confidence} confidence, a hypothesis): {gap.description}",
            _listed("Related features", gap.related_features),
            gap.caveat,
        )
        entries.append(_entry("gap", text, _value(gap.basis), _keys(COMPETITORS, gap.source_ids, known)))
    entries += [
        _labeled("differentiation", "Differentiation opportunity", item, COMPETITORS, known)
        for item in competitors.differentiation_opportunities
    ]
    entries += [_entry("query_used", _joined(f"Competitor search query used: {query}"), INTERPRETATION) for query in competitors.queries_used]
    quality = competitors.data_quality
    entries.append(_entry("data_quality", _joined(f"Competitor evidence level: {quality.evidence_level}", *quality.notes), INTERPRETATION))
    entries += [_entry("caveat", _joined(caveat), INTERPRETATION) for caveat in competitors.caveats]
    return entries


def _stored_keys(sources: list[StrategySourceKey]) -> tuple[str, ...]:
    keys: list[str] = []
    for source in sources:
        key = source_key(source.analysis, source.id)
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def _stored_number(stored_id: str, position: int) -> int:
    found = _STORED_ID.fullmatch(stored_id.strip().upper())
    return int(found.group(1)) if found else position


def _risk_facts(swot: SwotRiskResult | None) -> list[Fact]:
    facts: list[Fact] = []
    for position, risk in enumerate(swot.risks if swot else [], 1):
        text = _joined(
            f"Risk ({risk.category}; likelihood {risk.likelihood}, impact {risk.impact}, severity {risk.severity}): {risk.title}",
            risk.description,
            f"Mitigation: {risk.mitigation}",
            f"Early warning signal: {risk.early_warning_signal}",
        )
        if text:
            ref = f"{RISK_PREFIX}.{_stored_number(risk.id, position)}"
            facts.append(Fact(ref, "risk", text, risk.basis, _stored_keys(risk.sources)))
    return facts


def _feature_facts(mvp: MvpResult | None) -> list[Fact]:
    facts: list[Fact] = []
    for position, feature in enumerate(mvp.features if mvp else [], 1):
        essential = "essential" if feature.essential else "not essential"
        text = _joined(
            f"Feature ({feature.tier} tier, rank {feature.rank}, effort {feature.effort}, {essential}): {feature.name}",
            feature.description,
            f"User problem: {feature.user_problem}" if feature.user_problem else None,
        )
        if text:
            ref = f"{FEATURE_PREFIX}.{_stored_number(feature.id, position)}"
            facts.append(Fact(ref, "feature", text, feature.basis, _stored_keys(feature.sources)))
    return facts


def without_source_ids(text: str) -> str:
    return " ".join(_NAMED_IDS.sub(r"\1", _CITED_IDS.sub("", text)).split())


def _numbered(prefix: str, entries: list[Entry | None], *, hide_ids: bool = False) -> list[Fact]:
    kept = [entry for entry in entries if entry is not None]
    return [
        Fact(f"{prefix}.{number}", kind, without_source_ids(text) if hide_ids else text, basis, sources)
        for number, (kind, text, basis, sources) in enumerate(kept, 1)
    ]


def build_facts(
    idea: ExtractedIdea | None,
    constraints: StrategyConstraints | None = None,
    market: MarketOpportunityResult | None = None,
    competitors: CompetitorAnalysisResult | None = None,
    *,
    swot: SwotRiskResult | None = None,
    mvp: MvpResult | None = None,
) -> list[Fact]:
    return [
        *_numbered(IDEA_PREFIX, _idea_entries(idea)),
        *_numbered(CONSTRAINT_PREFIX, _constraint_entries(constraints)),
        *_numbered(MARKET_PREFIX, _market_entries(market), hide_ids=True),
        *_numbered(COMPETITOR_PREFIX, _competitor_entries(competitors), hide_ids=True),
        *_risk_facts(swot),
        *_feature_facts(mvp),
    ]


def fact_line(fact: Fact) -> str:
    return f"[{fact.ref}] ({fact.kind}) {fact.text}"


def render_facts(facts: Iterable[Fact]) -> str:
    return "\n".join([DIGEST_OPEN, *(fact_line(fact) for fact in facts), DIGEST_CLOSE])


def trim_queue(facts: list[Fact]) -> list[Fact]:
    queue: list[Fact] = []
    for kind, kept in TRIM_ORDER:
        of_kind = [fact for fact in facts if fact.kind == kind]
        queue += reversed(of_kind[kept:])
    return queue


def build_digest(
    idea: ExtractedIdea | None,
    constraints: StrategyConstraints | None = None,
    market: MarketOpportunityResult | None = None,
    competitors: CompetitorAnalysisResult | None = None,
    *,
    swot: SwotRiskResult | None = None,
    mvp: MvpResult | None = None,
    max_chars: int | None = None,
) -> Digest:
    limit = get_settings().strategy_digest_max_chars if max_chars is None else max_chars
    facts = build_facts(idea, constraints, market, competitors, swot=swot, mvp=mvp)
    length = len(render_facts(facts))
    dropped: list[str] = []
    for fact in trim_queue(facts):
        if length <= limit:
            break
        dropped.append(fact.ref)
        length -= len(fact_line(fact)) + 1
    kept = tuple(fact for fact in facts if fact.ref not in dropped)
    return Digest(facts=kept, text=render_facts(kept), max_chars=limit, dropped=tuple(dropped))
