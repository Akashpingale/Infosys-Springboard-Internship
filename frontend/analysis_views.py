"""Display helpers for the Milestone 2 result sections: market opportunity and competitors.

Pure functions with no Streamlit import, so every label, line and table row can be unit tested.
The basis of each claim is always written out as text, never shown by colour alone, and a value
that is not known is shown as not available rather than filled in.
"""

from agents.web_search_agent import render_markdown
from models.schemas import (
    COMPETITOR_TYPES,
    RISK_CATEGORIES,
    Competitor,
    CompetitorAnalysisResult,
    ComparisonCell,
    DataQuality,
    ExtractedIdea,
    GtmResult,
    LabeledItem,
    MarketGap,
    MarketOpportunityResult,
    MvpResult,
    PipelineResult,
    QuantEstimate,
    Segment,
    SourceRef,
    StrategySourceKey,
    SwotRiskResult,
    Trend,
)

BASIS_TEXT = {
    "sourced": "Sourced",
    "assumption": "Assumption",
    "ai_interpretation": "AI interpretation",
    "user_provided": "User provided",
}
STATUS_TEXT = {
    "sourced": "Sourced",
    "estimate_needs_verification": "Estimate, needs verification",
    "unavailable": "Unavailable",
}
CELL_TEXT = {
    "evidence_found": "Evidence found",
    "no_evidence_found": "No evidence found",
    "unclear": "Unclear",
}
TYPE_HEADINGS = {
    "direct": "Direct competitors",
    "indirect": "Indirect competitors and substitutes",
    "emerging": "Emerging competitors",
}
STAGE_LABELS = {"market_opportunity": "market opportunity", "competitor_analysis": "competitor analysis"}
FIGURES = (("tam", "TAM"), ("sam", "SAM"), ("som", "SOM"))

NOT_AVAILABLE = "Not available"
NO_IDS = "-"
MSG_NO_MARKET = (
    "No market opportunity analysis is available for this run. "
    "Any reason is listed in the notes at the top."
)
MSG_NO_COMPETITORS = (
    "No competitor analysis is available for this run. Any reason is listed in the notes at the top."
)
MSG_NONE_FOUND = "None found in the evidence."
MSG_NO_PRIORITY = "No priority segment could be chosen from the segments found."
MSG_NO_SOURCES = "No source was cited."
MSG_NO_COMPARISON = "No feature comparison could be made."
MSG_BROADER_MARKETS = (
    "Figures for a broader or different market. They are context only, "
    "not this idea's TAM, SAM or SOM."
)


def stage_label(stage: str) -> str:
    """Readable name for a stage or timing key. Milestone 1 names are shown unchanged."""
    return STAGE_LABELS.get(stage, stage)


def basis_text(basis: object) -> str:
    value = str(getattr(basis, "value", basis))
    return BASIS_TEXT.get(value, value)


def cited(source_ids: list[str]) -> str:
    """The cited evidence ids, for example 'S1, S3', or '' when nothing is cited."""
    return ", ".join(source_id.strip() for source_id in source_ids if source_id.strip())


def _labelled(text: str, label: str, source_ids: list[str]) -> str:
    ids = cited(source_ids)
    return f"{text} ({label}: {ids})" if ids else f"{text} ({label})"


def item_line(item: LabeledItem) -> str:
    """'text (Sourced: S1, S2)': the claim, its basis in words and the ids it cites."""
    return _labelled(item.text, basis_text(item.basis), item.source_ids)


def trend_line(trend: Trend) -> str:
    return _labelled(trend.trend, f"{trend.category.capitalize()}, {basis_text(trend.basis)}", trend.source_ids)


def segment_heading(segment: Segment) -> str:
    return f"{segment.name} (by {segment.segmentation_basis.replace('_', ' ')})"


def figure_row(name: str, figure: QuantEstimate) -> dict[str, str]:
    return {
        "Figure": name,
        "Value": figure.value or NOT_AVAILABLE,
        "Status": STATUS_TEXT.get(figure.status, figure.status),
        "Sources": cited(figure.source_ids) or NO_IDS,
        "Note": figure.note or "",
    }


def market_size_rows(market: MarketOpportunityResult) -> list[dict[str, str]]:
    """TAM, SAM and SOM with their status in words. An unknown figure stays not available."""
    return [figure_row(label, getattr(market.market_size, key)) for key, label in FIGURES]


def broader_market_rows(market: MarketOpportunityResult) -> list[dict[str, str]]:
    return [figure_row("Broader market", figure) for figure in market.broader_markets]


def quality_text(quality: DataQuality) -> str:
    return f"Evidence level: {quality.evidence_level.capitalize()}"


def _link_text(text: str) -> str:
    """Square brackets in a title would break the Markdown link around it."""
    return text.replace("[", "(").replace("]", ")").strip()


def source_lines(sources: list[SourceRef]) -> list[str]:
    """Each cited source as 'S1. [title](url)', in evidence order."""
    return [f"{source.id}. [{_link_text(source.title) or source.url}]({source.url})" for source in sources]


def competitor_groups(result: CompetitorAnalysisResult) -> list[tuple[str, list[Competitor]]]:
    """Competitors grouped by type, direct first; empty groups are left out."""
    groups = []
    for kind in COMPETITOR_TYPES:
        members = [competitor for competitor in result.competitors if competitor.type == kind]
        if members:
            groups.append((TYPE_HEADINGS[kind], members))
    return groups


def pricing_text(competitor: Competitor) -> str:
    price = competitor.pricing_model
    return _labelled(price.value or NOT_AVAILABLE, STATUS_TEXT.get(price.status, price.status), price.source_ids)


def competitor_facts(competitor: Competitor) -> list[tuple[str, str]]:
    """The facts shown for one competitor. A fact the evidence did not give is not available."""
    return [
        ("Basis", basis_text(competitor.basis)),
        ("Why it is relevant", competitor.relevance_note),
        ("Offering", competitor.offering or NOT_AVAILABLE),
        ("Target segment", competitor.target_segment or NOT_AVAILABLE),
        ("Key features", "; ".join(competitor.key_features) or NOT_AVAILABLE),
        ("Value proposition", competitor.value_proposition or NOT_AVAILABLE),
        ("Pricing", pricing_text(competitor)),
        ("Positioning", competitor.positioning or NOT_AVAILABLE),
        ("Difference from this idea", competitor.differentiation_vs_startup or NOT_AVAILABLE),
        ("Information found", competitor.info_completeness.capitalize()),
        ("Sources", cited(competitor.source_ids) or NO_IDS),
    ]


def cell_text(cell: ComparisonCell | None) -> str:
    if cell is None:
        return CELL_TEXT["unclear"]
    ids = cited(cell.source_ids)
    text = CELL_TEXT.get(cell.status, cell.status)
    return f"{text} ({ids})" if ids else text


def comparison_rows(result: CompetitorAnalysisResult) -> list[dict[str, str]]:
    """One row per competitor and one column per compared feature, with the cell status in words."""
    features = result.comparison.features
    rows = []
    for row in result.comparison.rows:
        cells = {cell.feature: cell for cell in row.cells}
        rows.append({"Competitor": row.competitor, **{feature: cell_text(cells.get(feature)) for feature in features}})
    return rows


def coverage_rows(result: CompetitorAnalysisResult) -> list[dict[str, str]]:
    """Per feature, how many competitors the evidence shows with it (counted in code)."""
    total = len(result.competitors)
    return [
        {"Feature": coverage.feature, "Competitors with evidence": f"{coverage.competitors_with_evidence} of {total}"}
        for coverage in result.comparison.feature_coverage
    ]


def gap_line(gap: MarketGap) -> str:
    """A gap is a hypothesis: its confidence and basis are always shown with it."""
    details = [f"{gap.confidence.capitalize()} confidence", basis_text(gap.basis)]
    if gap.related_features:
        details.append(f"related features: {'; '.join(gap.related_features)}")
    ids = cited(gap.source_ids)
    if ids:
        details.append(f"sources: {ids}")
    return f"{gap.description} ({'; '.join(details)})"


# --- the downloadable Markdown report ---------------------------------------------------------
# One document covering both milestones: the structured idea and web research from Milestone 1,
# then the market and competitor analyses from Milestone 2. Every line comes from the result;
# nothing is inferred here. When no analysis ran, the export stays exactly the Milestone 1
# research report, so the earlier behaviour is unchanged.

REPORT_TITLE = "Startup idea validation report"
RESEARCH_FILE_NAME = "market_research.md"
REPORT_FILE_NAME = "validation_report.md"
MSG_NO_RESEARCH = "No web research was collected for this run."
MSG_NO_IDEA = "The idea could not be structured, so nothing else could run. Any reason is listed in the errors above."


def has_analysis(result: PipelineResult) -> bool:
    return result.market is not None or result.competitors is not None


def report_file_name(result: PipelineResult) -> str:
    """The research file name until an analysis is present, then the full report name."""
    return REPORT_FILE_NAME if has_analysis(result) else RESEARCH_FILE_NAME


def _cell(value: object) -> str:
    """A table cell: one line, with pipes escaped so they cannot split the column."""
    return " ".join(str(value if value is not None else "").split()).replace("|", "\\|")


def _table(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    headers = list(rows[0])
    body = ["| " + " | ".join(_cell(row.get(header, "")) for header in headers) + " |" for row in rows]
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers), *body, ""]


def _demote(text: str) -> str:
    """Push every heading one level down, so a reused section nests under this report's title."""
    return "\n".join(f"#{line}" if line.startswith("#") else line for line in text.splitlines())


def _items(title: str, items: list[LabeledItem]) -> list[str]:
    if not items:
        return [f"**{title}**", "", MSG_NONE_FOUND, ""]
    return [f"**{title}**", "", *[f"- {item_line(item)}" for item in items], ""]


def _sources(sources: list[SourceRef]) -> list[str]:
    if not sources:
        return [MSG_NO_SOURCES, ""]
    return [*source_lines(sources), ""]


def _notes(analysis: MarketOpportunityResult | CompetitorAnalysisResult) -> list[str]:
    lines = [quality_text(analysis.data_quality), ""]
    if analysis.data_quality.notes:
        lines += [f"- {note}" for note in analysis.data_quality.notes] + [""]
    return lines


def idea_markdown(idea: ExtractedIdea) -> list[str]:
    return [
        "## What the system understood",
        "",
        f"**{idea.idea_title}**",
        "",
        f"- Industry: {idea.industry}",
        f"- Problem: {idea.problem}",
        f"- Solution: {idea.solution}",
        "- Target customers: " + "; ".join(idea.target_customers),
        "- Key features: " + "; ".join(idea.key_features),
        "",
    ]


def market_markdown(market: MarketOpportunityResult) -> list[str]:
    overview, demand = market.industry_overview, market.market_demand
    lines = ["## Market opportunity", "", *_notes(market)]
    lines += [
        "### Industry overview",
        "",
        f"- Market category: {overview.market_category}",
        "",
        overview.summary,
        "",
        *_items("Developments", overview.developments),
        "### Customer demand",
        "",
        demand.summary,
        "",
        *_items("Demand evidence", demand.demand_evidence),
        *_items("Customer problems", demand.customer_problems),
        *_items("Interest signals", demand.interest_signals),
        "### Market size",
        "",
        *_table(market_size_rows(market)),
    ]
    broader = broader_market_rows(market)
    if broader:
        lines += [MSG_BROADER_MARKETS, "", *_table(broader)]

    lines += ["### Trends", ""]
    lines += [f"- {trend_line(trend)}" for trend in market.trends] or [MSG_NONE_FOUND]
    lines += ["", "### Customer segments", ""]
    for segment in market.segments:
        lines += [f"**{segment_heading(segment)}**", "", segment.description, ""]
        if segment.needs:
            lines += [f"- Needs: {'; '.join(segment.needs)}", ""]
        lines += _items("Pain points", segment.pain_points)
    priority = market.priority_segment
    if priority is None:
        lines += [MSG_NO_PRIORITY, ""]
    else:
        lines += [f"**Priority segment: {priority.segment_name}**", "", priority.rationale, ""]
        lines += [f"- Risk: {risk}" for risk in priority.risks] + ([""] if priority.risks else [])

    lines += ["### Opportunities and limitations", ""]
    lines += _items("Opportunities", market.opportunities)
    lines += _items("Limitations", market.limitations)
    lines += [f"### Sources ({len(market.sources)})", "", *_sources(market.sources)]
    lines += [f"- {caveat}" for caveat in market.caveats] + ([""] if market.caveats else [])
    return lines


def competitor_markdown(analysis: CompetitorAnalysisResult) -> list[str]:
    lines = ["## Competitors", "", *_notes(analysis)]
    for heading, group in competitor_groups(analysis):
        lines += [f"### {heading} ({len(group)})", ""]
        for competitor in group:
            title = f"**{competitor.name}**"
            if competitor.website:
                title += f" ([website]({competitor.website}))"
            lines += [title, ""]
            lines += [f"- {label}: {text}" for label, text in competitor_facts(competitor)]
            lines += [""]
            lines += _items("Strengths", competitor.strengths)
            lines += _items("Weaknesses", competitor.weaknesses)

    lines += ["### Feature comparison", ""]
    rows = comparison_rows(analysis)
    if rows:
        lines += _table(rows)
        lines += _table(coverage_rows(analysis))
    else:
        lines += [MSG_NO_COMPARISON, ""]

    lines += ["### Market gaps and differentiation", ""]
    if analysis.market_gaps:
        for gap in analysis.market_gaps:
            lines += [f"- {gap_line(gap)}", f"  - {gap.caveat}"]
        lines += [""]
    else:
        lines += [MSG_NONE_FOUND, ""]
    lines += _items("Differentiation opportunities", analysis.differentiation_opportunities)

    if analysis.queries_used:
        lines += [f"### Searches run for this analysis ({len(analysis.queries_used)})", ""]
        lines += [f"- {query}" for query in analysis.queries_used] + [""]
    lines += [f"### Sources ({len(analysis.sources)})", "", *_sources(analysis.sources)]
    lines += [f"- {caveat}" for caveat in analysis.caveats] + ([""] if analysis.caveats else [])
    return lines


def report_markdown(result: PipelineResult, *, full: bool = False) -> str:
    """The downloadable report.

    With no market or competitor result this is exactly the Milestone 1 research report, so the
    earlier download is unchanged. With either analysis present it becomes the full report: run
    status, the structured idea, the web research, and whichever analyses exist.

    `full` (UI upgrade, KIRO_UI_UPGRADE_SPEC.md 10.5) always writes the full report, also when both
    analyses are missing: the status, the notes and errors that explain why, the idea or why it is
    missing, the research, and a line for each missing analysis. GET /api/runs/{id}/report.md uses
    it; the Streamlit download keeps the default.
    """
    if not full and not has_analysis(result):
        return render_markdown(result.search) if result.search is not None else ""

    lines = [f"# {REPORT_TITLE}", "", f"Status: {result.status.capitalize()}", ""]
    if result.timings:
        spent = ", ".join(f"{stage_label(stage)} {seconds:.1f}s" for stage, seconds in result.timings.items())
        lines += [f"Time taken: {spent}", ""]
    if result.warnings:
        lines += ["## Notes from this run", ""] + [f"- {warning}" for warning in result.warnings] + [""]
    if result.errors:
        lines += ["## Errors", ""]
        lines += [f"- {stage_label(item.stage)}: {item.message} ({item.code})" for item in result.errors]
        lines += [""]

    if result.idea is not None:
        lines += idea_markdown(result.idea)
    elif full:
        lines += ["## What the system understood", "", MSG_NO_IDEA, ""]
    if result.search is not None:
        lines += [_demote(render_markdown(result.search)), ""]
    else:
        lines += ["## Market and competitor research", "", MSG_NO_RESEARCH, ""]

    if result.market is not None:
        lines += market_markdown(result.market)
    else:
        lines += ["## Market opportunity", "", MSG_NO_MARKET, ""]
    if result.competitors is not None:
        lines += competitor_markdown(result.competitors)
    else:
        lines += ["## Competitors", "", MSG_NO_COMPETITORS, ""]
    if full and has_strategy(result):
        lines += strategy_markdown(result)
    return "\n".join(lines)


# --- Milestone 3: the strategy sections (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md D-14) ---------
# Only the full report (GET /api/runs/{id}/report.md) carries them, and only when a strategy part
# exists, so the default report and the Streamlit download stay exactly as they were. The Advisor
# conversation is not part of a result and is never exported. A strategy item's sources are those
# of the findings it is based on, named with their analysis ("market S3").

MSG_STRATEGY_CAVEAT = "These are AI interpretations of your results, not predictions."
MSG_NO_SWOT = "No SWOT and risk analysis is available for this run. Any reason is listed in the notes at the top."
MSG_NO_MVP = "No MVP recommendation is available for this run. Any reason is listed in the notes at the top."
MSG_NO_GTM = "No go-to-market plan is available for this run. Any reason is listed in the notes at the top."
MSG_NONE_IN_RUN = "None found in this run."
MSG_COVERAGE_GAP = "Not checked is not the same as safe."
MSG_OVER_CAPACITY = "The essential features need more effort than the team and time allow."
MSG_BUDGET_CONFLICT = "May cost more than a bootstrapped budget."
SWOT_QUADRANTS = (
    ("strengths", "Strengths"),
    ("weaknesses", "Weaknesses"),
    ("opportunities", "Opportunities"),
    ("threats", "Threats"),
)
SEVERITIES = ("high", "medium", "low")
CONSTRAINT_TEXT = (
    ("team_size", "Team size"),
    ("months_to_mvp", "Months to the first release"),
    ("budget_level", "Budget"),
    ("technical_skill", "Technical skill"),
    ("launch_region", "Launch region"),
)
CONSTRAINT_VALUES = {
    "bootstrapped": "Bootstrapped",
    "small": "Small budget",
    "funded": "Funded",
    "non_technical": "Non-technical",
    "some": "Some technical",
    "strong": "Strong technical team",
}
ORIGIN_TEXT = {
    "founder_listed": "Your feature",
    "gap_opportunity": "Suggested from a possible gap",
    "suggested": "Suggested",
}
TIER_HEADINGS = (("mvp", "In the first release"), ("later", "Later"))


def has_strategy(result: PipelineResult) -> bool:
    return result.swot is not None or result.mvp is not None or result.gtm is not None


def strategy_cited(sources: list[StrategySourceKey]) -> list[str]:
    """Inherited sources named with their analysis, for example 'market S3'."""
    return [f"{source.analysis} {source.id}" for source in sources]


def strategy_line(text: str, basis: str, sources: list[StrategySourceKey]) -> str:
    return _labelled(text, basis_text(basis), strategy_cited(sources))


def _words(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _basis_facts(basis: str, sources: list[StrategySourceKey]) -> list[str]:
    return [f"- Basis: {basis_text(basis)}", f"- Sources: {cited(strategy_cited(sources)) or NO_IDS}"]


def _strings(title: str, values: list[str]) -> list[str]:
    return [f"**{title}**", "", *[f"- {value}" for value in values], ""] if values else []


def _summary(text: str) -> list[str]:
    return [_labelled(text, basis_text("ai_interpretation"), []), ""] if text else []


def swot_markdown(swot: SwotRiskResult) -> list[str]:
    lines = ["## SWOT and risks", "", MSG_STRATEGY_CAVEAT, "", *_summary(swot.summary)]
    for name, title in SWOT_QUADRANTS:
        lines += [f"**{title}**", ""]
        for item in getattr(swot, name):
            lines.append(f"- {strategy_line(item.text, item.basis, item.sources)}")
            if item.why_it_matters:
                lines.append(f"  - Why it matters: {item.why_it_matters}")
        lines += [""] if getattr(swot, name) else [MSG_NONE_IN_RUN, ""]

    counts = ", ".join(f"{sum(1 for risk in swot.risks if risk.severity == level)} {level}" for level in SEVERITIES)
    lines += [f"### Risks ({len(swot.risks)})", "", f"{len(swot.risks)} risks: {counts}.", ""]
    coverage = "; ".join(f"{category} {swot.risk_category_coverage.get(category, 0)}" for category in RISK_CATEGORIES)
    lines += [f"Risk categories: {coverage}.", ""]
    if swot.coverage_gaps:
        lines += [f"No {' or '.join(swot.coverage_gaps)} risk was found. {MSG_COVERAGE_GAP}", ""]
    for risk in swot.risks:
        lines += [f"**{risk.title}** ({risk.severity.capitalize()} severity, {risk.category})", ""]
        lines += [
            f"- What could happen: {risk.description}",
            f"- Likelihood: {risk.likelihood.capitalize()}. Impact: {risk.impact.capitalize()}. "
            f"Confidence: {risk.confidence.capitalize()}.",
            f"- Mitigation: {risk.mitigation}",
            f"- Early warning sign: {risk.early_warning_signal}",
            *_basis_facts(risk.basis, risk.sources),
            "",
        ]
    return lines + _strings("Limitations", swot.limitations)


def _constraint_lines(mvp: MvpResult) -> list[str]:
    used = mvp.constraints_used
    lines = []
    for name, label in CONSTRAINT_TEXT:
        value = getattr(used, name)
        if value is not None:
            assumed = " (assumed)" if name in mvp.quality.constraints_assumed else ""
            lines.append(f"- {label}: {CONSTRAINT_VALUES.get(str(value), value)}{assumed}")
    return ["**Resources the plan is built on**", "", *lines, ""] if lines else []


def mvp_markdown(mvp: MvpResult, swot: SwotRiskResult | None) -> list[str]:
    risks = {risk.id: risk.title for risk in swot.risks} if swot is not None else {}
    lines = ["## MVP recommendation", "", MSG_STRATEGY_CAVEAT, "", *_summary(mvp.summary)]
    lines += [f"Planned {mvp.planned_person_months:g} of {mvp.capacity_person_months:g} person-months.", ""]
    if mvp.over_capacity:
        lines += [MSG_OVER_CAPACITY, ""]
    lines += _constraint_lines(mvp)
    for tier, heading in TIER_HEADINGS:
        features = sorted((feature for feature in mvp.features if feature.tier == tier), key=lambda feature: feature.rank)
        lines += [f"### {heading} ({len(features)})", ""]
        if not features:
            lines += [MSG_NONE_IN_RUN, ""]
        for feature in features:
            lines += [f"**Rank {feature.rank}: {feature.name}** ({ORIGIN_TEXT.get(feature.origin, feature.origin)})", ""]
            if feature.description:
                lines.append(f"- {feature.description}")
            if feature.user_problem:
                lines.append(f"- User problem: {feature.user_problem}")
            lines += [
                f"- Score: {feature.score:g} (need {feature.customer_need}, differentiation {feature.differentiation}, "
                f"feasibility {feature.feasibility})",
                f"- Effort: {feature.effort}, AI estimate",
            ]
            if feature.rationale:
                lines.append(f"- Why: {feature.rationale}")
            linked = [risks[risk_id] for risk_id in feature.mitigates_risk_ids if risk_id in risks]
            if linked:
                lines.append(f"- Lowers the risks: {'; '.join(linked)}")
            if feature.id in mvp.deferred_reasons:
                lines.append(f"- Why later: {mvp.deferred_reasons[feature.id]}")
            lines += [*_basis_facts(feature.basis, feature.sources), ""]
    lines += ["### Success metrics", ""]
    for metric in mvp.success_metrics:
        target = f" Suggested target: {metric.suggested_target.rstrip('.')}." if metric.suggested_target else ""
        text = f"{metric.name}: {metric.how_to_measure.rstrip('.')}.{target}"
        lines.append(f"- {_labelled(text, basis_text(metric.basis), [])}")
    lines += [""] if mvp.success_metrics else [MSG_NONE_IN_RUN, ""]
    return lines + _strings("Limitations", mvp.limitations)


def gtm_markdown(gtm: GtmResult, mvp: MvpResult | None, swot: SwotRiskResult | None) -> list[str]:
    features = {feature.id: feature.name for feature in mvp.features} if mvp is not None else {}
    risks = {risk.id: risk.title for risk in swot.risks} if swot is not None else {}
    stated = gtm.positioning
    lines = ["## Go-to-market plan", "", MSG_STRATEGY_CAVEAT, "", *_summary(gtm.summary)]
    lines += ["### Positioning", "", stated.statement, ""]
    lines += [
        f"- Target segment: {stated.target_segment}",
        f"- For: {stated.for_whom}",
        f"- Problem: {stated.problem}",
        f"- Category: {stated.category}",
        f"- Key benefit: {stated.key_benefit}",
        f"- Alternative: {stated.alternative}",
        f"- Differentiator ({stated.differentiator_status.capitalize()}): {stated.differentiator}",
        *_basis_facts(stated.basis, stated.sources),
        "",
    ]
    lines += [f"### Channels ({len(gtm.channels)})", ""]
    for channel in sorted(gtm.channels, key=lambda entry: entry.priority):
        start = " (Start here)" if channel.start_here else ""
        lines += [f"**Rank {channel.priority}: {channel.name}**{start}", ""]
        lines += [
            f"- Kind: {_words(channel.kind)}. Role: {_words(channel.role)}.",
            f"- Audience fit: {channel.audience_fit} of 5. Cost: {channel.cost_level.capitalize()}. "
            f"Time to a first result: {channel.speed_to_first_result.capitalize()}.",
        ]
        if channel.fit_rationale:
            lines.append(f"- Why it fits: {channel.fit_rationale}")
        lines += [f"- First experiment: {channel.first_experiment}", f"- Success signal: {channel.success_signal}"]
        used = [features[feature_id] for feature_id in channel.uses_feature_ids if feature_id in features]
        if used:
            lines.append(f"- Uses the features: {'; '.join(used)}")
        addressed = [risks[risk_id] for risk_id in channel.addresses_risk_ids if risk_id in risks]
        if addressed:
            lines.append(f"- Addresses the risks: {'; '.join(addressed)}")
        if channel.budget_conflict:
            lines.append(f"- Budget: {MSG_BUDGET_CONFLICT}")
        lines += [*_basis_facts(channel.basis, channel.sources), ""]
    lines += ["### Early customers", ""]
    for tactic in gtm.early_customers:
        lines += [f"**{tactic.tactic}**", ""]
        lines += [
            f"- Where to find them: {tactic.where_to_find_them}",
            f"- Offer: {tactic.offer}",
            f"- How to measure: {tactic.how_to_measure}",
            *_basis_facts(tactic.basis, tactic.sources),
            "",
        ]
    if not gtm.early_customers:
        lines += [MSG_NONE_IN_RUN, ""]
    lines += ["### Launch plan", ""]
    for number, phase in enumerate(gtm.launch_phases, 1):
        lines.append(f"{number}. **{phase.name}**: {phase.goal}")
        lines += [f"   - {action}" for action in phase.actions]
    lines += [""]
    lines += ["### Key messages", ""]
    rows = [{"Audience": entry.audience, "Message": entry.message, "Proof needed": entry.proof_needed}
            for entry in gtm.key_messages]
    lines += _table(rows) or [MSG_NONE_IN_RUN, ""]
    return lines + _strings("Limitations", gtm.limitations)


def strategy_markdown(result: PipelineResult) -> list[str]:
    """The three strategy sections, each saying so when its part is missing."""
    lines = swot_markdown(result.swot) if result.swot is not None else ["## SWOT and risks", "", MSG_NO_SWOT, ""]
    if result.mvp is not None:
        lines += mvp_markdown(result.mvp, result.swot)
    else:
        lines += ["## MVP recommendation", "", MSG_NO_MVP, ""]
    if result.gtm is not None:
        lines += gtm_markdown(result.gtm, result.mvp, result.swot)
    else:
        lines += ["## Go-to-market plan", "", MSG_NO_GTM, ""]
    return lines
