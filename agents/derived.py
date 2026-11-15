"""Fields derived in code from a finished pipeline result (KIRO_UI_UPGRADE_SPEC.md 8.5 and 10.4).

Everything here is deterministic and uses only the structured results the agents already checked:
no LLM call, no new figure, no new source. `with_derived_fields` adds the notices, the evidence
strength, the executive summary and the "what to verify next" list to a PipelineResult, and never
lets a problem here fail a run.
"""

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel

from agents.mvp_agent import ASSUMED_PARTS
from agents.notices import STAGE_GTM, STAGE_MVP, STAGE_SWOT, build_notices
from models.schemas import (
    Basis,
    Channel,
    CompetitorAnalysisResult,
    EvidenceComponent,
    EvidenceStrength,
    MarketOpportunityResult,
    MvpFeature,
    PipelineResult,
    RiskItem,
    StrategySourceKey,
    SummaryLine,
    VerifyItem,
)

logger = logging.getLogger(__name__)

MARKET, COMPETITORS = "market", "competitors"

# Section 8.5, exactly: the three weights, the breadth cap, the level values and the label bands.
WEIGHTS = {"sourced_share": 0.40, "source_breadth": 0.30, "evidence_level": 0.30}
BREADTH_CAP = 8
LEVEL_VALUES = {"strong": 1.0, "limited": 0.5, "insufficient": 0.0}
STRONG_AT = 0.70
MODERATE_AT = 0.40
CAPTION = "How well the findings are backed by sources. This is not a prediction of success."
COMPONENT_LABELS = {
    "sourced_share": "Sourced share",
    "source_breadth": "Source breadth",
    "evidence_level": "Evidence level",
}
_EPSILON = 1e-9  # so 0.4 + 0.3 lands on Strong despite floating-point rounding

FIGURES = (("tam", "TAM"), ("sam", "SAM"), ("som", "SOM"))
TYPE_ORDER = ("direct", "indirect", "emerging")
GAP_ORDER = {"medium": 0, "low": 1}
MSG_NO_MARKET_SIZE = "No reliable market size was found for this idea's own market."

# Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 12.5): the strategy lines. A line
# names one analysis, so a strategy item's inherited sources are given for the analysis most of
# them come from (the first one named on a tie).
STRATEGY_RESULTS = ((STAGE_SWOT, "swot"), (STAGE_MVP, "mvp"), (STAGE_GTM, "gtm"))
LEVEL_RANK = {"high": 0, "medium": 1, "low": 2}
MVP_SUMMARY_FEATURES = 3
CONSTRAINT_WORDS = {"team_size": "team size", "months_to_mvp": "timeline"}


# --- evidence strength (Section 8.5) ---------------------------------------------------------------


def strength_label(score: float) -> str:
    """Strong at 0.70 or above, Moderate from 0.40, Limited below 0.40."""
    if score + _EPSILON >= STRONG_AT:
        return "strong"
    if score + _EPSILON >= MODERATE_AT:
        return "moderate"
    return "limited"


def labeled_bases(model: BaseModel | None) -> list[str]:
    """The basis of every labelled item in an analysis: claims, trends, gaps and competitors."""
    found: list[str] = []
    if model is None:
        return found
    basis = getattr(model, "basis", None)
    value = str(getattr(basis, "value", basis)) if basis is not None else None
    if value in {member.value for member in Basis}:
        found.append(value)
    for name in type(model).model_fields:
        child = getattr(model, name)
        for item in child if isinstance(child, list) else [child]:
            if isinstance(item, BaseModel):
                found.extend(labeled_bases(item))
    return found


def source_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def _domains(market: MarketOpportunityResult | None, competitors: CompetitorAnalysisResult | None) -> set[str]:
    sources = [*(market.sources if market else []), *(competitors.sources if competitors else [])]
    return {domain for domain in (source_domain(source.url) for source in sources) if domain}


def evidence_strength(result: PipelineResult) -> EvidenceStrength | None:
    """None when neither analysis exists: there is nothing to rate. With one analysis, the rating
    uses that one alone."""
    market, competitors = result.market, result.competitors
    if market is None and competitors is None:
        return None

    bases = [*labeled_bases(market), *labeled_bases(competitors)]
    sourced = bases.count(Basis.sourced.value)
    share = sourced / len(bases) if bases else 0.0

    domains = len(_domains(market, competitors))
    breadth = min(domains, BREADTH_CAP) / BREADTH_CAP

    rated = [(name, analysis.data_quality.evidence_level) for name, analysis in ((MARKET, market), (COMPETITORS, competitors)) if analysis]
    level = sum(LEVEL_VALUES[value] for _, value in rated) / len(rated)

    score = WEIGHTS["sourced_share"] * share + WEIGHTS["source_breadth"] * breadth + WEIGHTS["evidence_level"] * level
    claims = "claim" if len(bases) == 1 else "claims"
    components = [
        EvidenceComponent(
            key="sourced_share", label=COMPONENT_LABELS["sourced_share"], weight=WEIGHTS["sourced_share"],
            value=round(share, 4), detail=f"{sourced} of {len(bases)} labelled {claims} are backed by a cited source.",
        ),
        EvidenceComponent(
            key="source_breadth", label=COMPONENT_LABELS["source_breadth"], weight=WEIGHTS["source_breadth"],
            value=round(breadth, 4),
            detail=f"{domains} distinct source {'website' if domains == 1 else 'websites'}, counted up to {BREADTH_CAP}.",
        ),
        EvidenceComponent(
            key="evidence_level", label=COMPONENT_LABELS["evidence_level"], weight=WEIGHTS["evidence_level"],
            value=round(level, 4),
            detail="; ".join(f"{'Market' if name == MARKET else 'Competitor'} evidence rated {value}" for name, value in rated) + ".",
        ),
    ]
    return EvidenceStrength(label=strength_label(score), score=round(min(max(score, 0.0), 1.0), 4), components=components, caption=CAPTION)


# --- executive summary (Section 10.4) ---------------------------------------------------------


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    return text if not text or text.endswith((".", "!", "?")) else f"{text}."


def _market_size_line(market: MarketOpportunityResult) -> SummaryLine:
    for name, label in FIGURES:
        figure = getattr(market.market_size, name)
        if figure.status == "sourced" and figure.value:
            note = f" ({figure.note.rstrip('.')})" if figure.note else ""
            return SummaryLine(topic="market_size", text=_sentence(f"Market size ({label}): {figure.value}{note}"),
                               basis=Basis.sourced, source_ids=list(figure.source_ids), analysis=MARKET)
    for name, label in FIGURES:
        figure = getattr(market.market_size, name)
        if figure.status == "estimate_needs_verification" and figure.value:
            return SummaryLine(topic="market_size",
                               text=_sentence(f"Estimated {label}: {figure.value}. It needs verification"),
                               basis=None, source_ids=list(figure.source_ids), analysis=MARKET)
    return SummaryLine(topic="market_size", text=MSG_NO_MARKET_SIZE, analysis=MARKET)


def _first_claim(items: list) -> object | None:
    return next((item for item in items if item.basis is Basis.sourced), items[0] if items else None)


def executive_summary(result: PipelineResult) -> list[SummaryLine]:
    """Up to six lines, in this order: market size, demand, priority segment, competitors found, the
    most confident gap, the main limitation. Claim text is quoted from the checked results with its
    own basis and sources; code only adds the lead-in words."""
    market, competitors = result.market, result.competitors
    lines: list[SummaryLine] = []
    if market is not None:
        lines.append(_market_size_line(market))
        demand = _first_claim(market.market_demand.demand_evidence)
        if demand is not None:
            lines.append(SummaryLine(topic="demand", text=_sentence(f"Demand: {demand.text}"), basis=demand.basis,
                                     source_ids=list(demand.source_ids), analysis=MARKET))
        priority = market.priority_segment
        if priority is not None:
            segment = next((s for s in market.segments if s.name == priority.segment_name), None)
            lines.append(SummaryLine(
                topic="priority_segment",
                text=_sentence(f"Priority segment: {priority.segment_name}. {priority.rationale}"),
                basis=Basis.ai_interpretation, source_ids=list(segment.source_ids) if segment else [], analysis=MARKET,
            ))
    if competitors is not None:
        counts = {kind: sum(1 for c in competitors.competitors if c.type == kind) for kind in TYPE_ORDER}
        total = sum(counts.values())
        if total == 1:
            text = f"1 competitor found ({next(kind for kind in TYPE_ORDER if counts[kind])})."
        else:
            parts = [f"{counts[kind]} {kind}" for kind in TYPE_ORDER if counts[kind]]
            joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" and {parts[-1]}"
            text = f"{total} competitors found: {joined}."
        lines.append(SummaryLine(topic="competitors", text=text, analysis=COMPETITORS))
        gaps = sorted(competitors.market_gaps, key=lambda gap: GAP_ORDER.get(gap.confidence, len(GAP_ORDER)))
        if gaps:
            gap = gaps[0]
            lines.append(SummaryLine(
                topic="gap", text=_sentence(f"Possible gap ({gap.confidence} confidence, a hypothesis): {gap.description}"),
                basis=gap.basis, source_ids=list(gap.source_ids), analysis=COMPETITORS,
            ))
    if market is not None and market.limitations:
        limitation = _first_claim(market.limitations)
        lines.append(SummaryLine(topic="limitation", text=_sentence(f"Main limitation: {limitation.text}"),
                                 basis=limitation.basis, source_ids=list(limitation.source_ids), analysis=MARKET))
    return lines + strategy_summary(result)


# --- strategy lines (Milestone 3, Section 12.5) -----------------------------------------------


def _and(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + f" and {labels[-1]}"


def strategy_sources(sources: Iterable[StrategySourceKey]) -> tuple[str | None, list[str]]:
    """The analysis and the source ids a strategy line carries: those of the analysis most of the
    inherited sources come from, the first one named on a tie."""
    keys = list(dict.fromkeys((source.analysis, source.id) for source in sources))
    if not keys:
        return None, []
    counts = Counter(analysis for analysis, _ in keys)
    analysis = max(counts, key=counts.__getitem__)
    return analysis, [source_id for name, source_id in keys if name == analysis]


def _shared_basis(bases: Sequence[str]) -> str:
    return bases[0] if len(set(bases)) == 1 else Basis.ai_interpretation.value


def top_risk(result: PipelineResult) -> RiskItem | None:
    """The highest-severity risk, then the highest impact; the first listed on a tie."""
    risks = result.swot.risks if result.swot is not None else []
    return min(risks, key=lambda risk: (LEVEL_RANK[risk.severity], LEVEL_RANK[risk.impact]), default=None)


def first_release(result: PipelineResult) -> list[MvpFeature]:
    features = result.mvp.features if result.mvp is not None else []
    return sorted((feature for feature in features if feature.tier == "mvp"), key=lambda feature: feature.rank)


def start_channel(result: PipelineResult) -> Channel | None:
    channels = result.gtm.channels if result.gtm is not None else []
    return next((channel for channel in channels if channel.start_here), None)


def strategy_summary(result: PipelineResult) -> list[SummaryLine]:
    """Up to three lines, built from the stored strategy results: the highest-severity risk, the top
    three features of the first release and the channel to start with. Nothing when there is no
    strategy."""
    lines: list[SummaryLine] = []
    risk = top_risk(result)
    if risk is not None:
        analysis, ids = strategy_sources(risk.sources)
        text = f"Main risk ({risk.severity} severity, {risk.category}): {risk.title}"
        lines.append(SummaryLine(topic="top_risk", text=_sentence(text), basis=risk.basis, source_ids=ids, analysis=analysis))
    features = first_release(result)
    if features:
        top = features[:MVP_SUMMARY_FEATURES]
        names = _and([feature.name for feature in top])
        if len(features) > len(top):
            text = f"First release, the top {len(top)} of {len(features)} features: {names}"
        else:
            text = f"First release ({len(features)} {'feature' if len(features) == 1 else 'features'}): {names}"
        analysis, ids = strategy_sources(source for feature in top for source in feature.sources)
        basis = _shared_basis([feature.basis for feature in top])
        lines.append(SummaryLine(topic="mvp_scope", text=_sentence(text), basis=basis, source_ids=ids, analysis=analysis))
    channel = start_channel(result)
    if channel is not None:
        analysis, ids = strategy_sources(channel.sources)
        lines.append(SummaryLine(topic="start_channel", text=_sentence(f"Go-to-market, start here: {channel.name}"),
                                 basis=channel.basis, source_ids=ids, analysis=analysis))
    return lines


def strategy_verify_next(result: PipelineResult) -> list[VerifyItem]:
    """Each high-severity risk held with low confidence (its early-warning signal), the constraints
    the MVP plan assumed, and the first experiment of the channel to start with."""
    items: list[VerifyItem] = []
    for risk in result.swot.risks if result.swot is not None else []:
        if risk.severity == "high" and risk.confidence == "low":
            analysis, ids = strategy_sources(risk.sources)
            items.append(VerifyItem(topic="risk", analysis=analysis, source_ids=ids, text=_sentence(
                f"Check the high-severity risk \"{risk.title}\", which has low confidence. Early warning sign: "
                f"{risk.early_warning_signal}"
            )))
    mvp = result.mvp
    assumed = [name for name in mvp.quality.constraints_assumed if name in ASSUMED_PARTS] if mvp is not None else []
    if assumed:
        words = _and([CONSTRAINT_WORDS[name] for name in assumed])
        values = _and([ASSUMED_PARTS[name].format(value=getattr(mvp.constraints_used, name)) for name in assumed])
        items.append(VerifyItem(topic="constraints", text=f"Confirm your {words}: the MVP plan assumes {values}."))
    channel = start_channel(result)
    if channel is not None:
        analysis, ids = strategy_sources(channel.sources)
        items.append(VerifyItem(topic="channel", analysis=analysis, source_ids=ids,
                                text=_sentence(f"Run the first experiment for {channel.name}: {channel.first_experiment}")))
    return items


def strategy_inputs_missing(result: PipelineResult) -> dict[str, list[str]]:
    """Per strategy stage with a result, the inputs it was written without (for its notice)."""
    found: dict[str, list[str]] = {}
    for stage, name in STRATEGY_RESULTS:
        value = getattr(result, name)
        if value is not None and value.quality.inputs_missing:
            found[stage] = list(value.quality.inputs_missing)
    return found


# --- what to verify next (Section 10.4) -------------------------------------------------------


def _join(labels: list[str]) -> str:
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + f" or {labels[-1]}"


def verify_next(result: PipelineResult) -> list[VerifyItem]:
    """Every unavailable, estimated or low-confidence part of the analyses, as a checklist item."""
    market, competitors = result.market, result.competitors
    items: list[VerifyItem] = []
    if market is not None:
        missing = [label for name, label in FIGURES if getattr(market.market_size, name).status == "unavailable"]
        if missing:
            items.append(VerifyItem(topic="market_size", analysis=MARKET, text=(
                f"Find a reliable market size for this idea's own market: no source confirmed the {_join(missing)}."
            )))
        for name, label in FIGURES:
            figure = getattr(market.market_size, name)
            if figure.status == "estimate_needs_verification" and figure.value:
                items.append(VerifyItem(topic="market_size", analysis=MARKET, source_ids=list(figure.source_ids),
                                        text=f"Check the {label} estimate of {figure.value} against its source."))
        for figure in market.broader_markets:
            if figure.status == "estimate_needs_verification" and figure.value:
                items.append(VerifyItem(topic="broader_market", analysis=MARKET, source_ids=list(figure.source_ids),
                                        text=f"Check the broader-market figure of {figure.value} against its source."))
        if market.priority_segment is None:
            items.append(VerifyItem(topic="priority_segment", analysis=MARKET,
                                    text="Choose a priority segment: none could be chosen from the evidence."))
        if market.data_quality.evidence_level != "strong":
            items.append(VerifyItem(topic="evidence", analysis=MARKET, text=(
                f"Look for stronger market sources: the market evidence was rated {market.data_quality.evidence_level}."
            )))
    if competitors is not None:
        for competitor in competitors.competitors:
            price = competitor.pricing_model
            if price.status == "estimate_needs_verification" and price.value:
                items.append(VerifyItem(topic="pricing", analysis=COMPETITORS, source_ids=list(price.source_ids),
                                        text=f"Check the pricing for {competitor.name} ({price.value}) against its source."))
            if competitor.info_completeness == "minimal":
                items.append(VerifyItem(topic="competitor", analysis=COMPETITORS, source_ids=list(competitor.source_ids),
                                        text=f"Find out more about {competitor.name}: the sources gave little detail."))
        for gap in competitors.market_gaps:
            if gap.confidence == "low":
                items.append(VerifyItem(topic="gap", analysis=COMPETITORS, source_ids=list(gap.source_ids),
                                        text=_sentence(f"Test the low-confidence gap: {gap.description}")))
        if competitors.data_quality.evidence_level != "strong":
            items.append(VerifyItem(topic="evidence", analysis=COMPETITORS, text=(
                "Look for stronger competitor sources: the competitor evidence was rated "
                f"{competitors.data_quality.evidence_level}."
            )))
    return items + strategy_verify_next(result)


# --- all together -----------------------------------------------------------------------------


def with_derived_fields(result: PipelineResult) -> PipelineResult:
    """The result with notices, evidence strength, executive summary and verify-next filled in.
    A problem here is logged and leaves the result as it was, so it can never fail a run."""
    try:
        return result.model_copy(update={
            "notices": build_notices(result.warnings, result.errors, strategy_inputs_missing(result)),
            "evidence_strength": evidence_strength(result),
            "executive_summary": executive_summary(result),
            "verify_next": verify_next(result),
        })
    except Exception as exc:  # noqa: BLE001 - derived fields are optional extras
        logger.warning("derived result fields were not added (%s)", type(exc).__name__)
        return result
