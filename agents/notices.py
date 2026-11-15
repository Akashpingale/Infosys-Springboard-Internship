"""Plain-language quality notes (KIRO_UI_UPGRADE_SPEC.md Sections 6.7 and 10.3).

The agents and the orchestrator write `warnings` in technical terms, often starting with the field
they repaired ("market_demand.demand_evidence[1]: ..."). Those stay unchanged in PipelineResult.
`build_notices` turns each stage error and each warning into a Notice whose `message` is plain and
never names a field, an index or an evidence id; the original text is kept in `detail`. Wording
this module does not know gets a general message, so a new warning can never leak a field path.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from agents.competitor_analysis_agent import STAGE_COMPETITOR
from agents.competitor_analysis_agent import WARNING_PREFIX as COMPETITOR_PREFIX
from agents.market_opportunity_agent import STAGE_MARKET
from agents.market_opportunity_agent import WARNING_PREFIX as MARKET_PREFIX
from agents.strategy_checks import (
    BASIS_ADJUSTED,
    DUPLICATE_REMOVED,
    FIGURE_REMOVED,
    ITEMS_CUT,
    OVERCLAIM_REMOVED,
    REF_REMOVED,
    TEXT_SHORTENED,
)
from models.schemas import Notice, StageError

STAGE_EXTRACTION = "extraction"
STAGE_SEARCH = "search"
# Milestone 3 (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md Section 5.1): the strategy stages, as
# orchestrator.py names them, and their labels, which also start their warnings. Kept apart from
# STAGE_TITLES, the stages of every run, since only a run with strategy has these.
STAGE_SWOT = "swot_risk"
STAGE_MVP = "mvp_recommendation"
STAGE_GTM = "go_to_market"
STRATEGY_TITLES = {
    STAGE_SWOT: "Assessing strengths and risks",
    STAGE_MVP: "Recommending MVP features",
    STAGE_GTM: "Planning go-to-market",
}

# Section 6.7 stage labels, also used by the run API and /api/meta.
STAGE_TITLES = {
    STAGE_EXTRACTION: "Understanding your idea",
    STAGE_SEARCH: "Searching the web",
    STAGE_MARKET: "Analysing the market",
    STAGE_COMPETITOR: "Comparing competitors",
}
# The labels that start a stage's warnings: the agents' WARNING_PREFIX and the orchestrator's own.
WARNING_LABELS = {
    MARKET_PREFIX: STAGE_MARKET,
    COMPETITOR_PREFIX: STAGE_COMPETITOR,
    "Idea extraction": STAGE_EXTRACTION,
    "Web search": STAGE_SEARCH,
    **{title: stage for stage, title in STRATEGY_TITLES.items()},
}
AREAS = {
    STAGE_EXTRACTION: "the extracted idea",
    STAGE_SEARCH: "the web search results",
    STAGE_MARKET: "the market analysis",
    STAGE_COMPETITOR: "the competitor analysis",
}
# Milestone 3 (Sections 11.3 and 11.4): what each strategy stage writes, for the general message,
# and the plain names of the inputs a strategy stage can be written without.
STRATEGY_AREAS = {
    STAGE_SWOT: "the strengths and risks",
    STAGE_MVP: "the MVP plan",
    STAGE_GTM: "the go-to-market plan",
}
INPUT_NAMES = {
    "market": "the market analysis",
    "competitors": "the competitor analysis",
    "swot": "the risk analysis",
    "mvp": "the feature plan",
}
TITLES = {**STAGE_TITLES, **STRATEGY_TITLES}

INFO, WARNING, ERROR = "info", "warning", "error"
CODE_FALLBACK = "quality_adjusted"
CODE_CANCELLED = "run_cancelled"
CODE_INPUTS_MISSING = "strategy_inputs_missing"
CODE_STRATEGY_SKIPPED = "strategy_stage_skipped"
CODE_CONSTRAINTS_ASSUMED = "mvp_constraints_assumed"
CODE_OVER_CAPACITY = "mvp_over_capacity"
CODE_BUDGET_CONFLICT = "gtm_budget_conflict"
CODE_SEGMENTS_MISSING = "gtm_segments_missing"

# The last field of a path names what was repaired: "competitors[0].strengths[1]" is a strength.
NOUNS = {
    "demand_evidence": "demand claim",
    "customer_problems": "customer problem",
    "interest_signals": "interest signal",
    "developments": "industry development",
    "trends": "trend",
    "pain_points": "pain point",
    "needs": "customer need",
    "segments": "customer segment",
    "priority_segment": "priority segment",
    "risks": "risk",
    "opportunities": "opportunity",
    "limitations": "limitation",
    "strengths": "competitor strength",
    "weaknesses": "competitor weakness",
    "key_features": "competitor feature",
    "pricing_model": "competitor price",
    "website": "competitor website",
    "competitors": "competitor",
    "candidates": "possible competitor",
    "differentiation_opportunities": "differentiation opportunity",
    "market_gaps": "possible gap",
    "comparison": "comparison cell",
    "tam": "market figure",
    "sam": "market figure",
    "som": "market figure",
    "broader_markets": "market figure",
    "industry_overview": "industry overview point",
    "market_demand": "demand point",
}
DEFAULT_NOUN = "finding"

# Why a competitor or a candidate was removed (agents/competitor_checks.py), in plain words.
REMOVAL_REASONS = {
    "it is not named in its cited sources": "its sources do not name it",
    "it has no valid source": "no source supports it",
    "the founder did not name it in the submission": (
        "it was listed as named by you, but your submission does not mention it"
    ),
}
DEFAULT_REMOVAL_REASON = "it could not be confirmed from the sources"
NAME_MAX = 80

_PREFIX = re.compile(r"^(?P<label>" + "|".join(map(re.escape, WARNING_LABELS)) + r"): (?P<rest>.*)$", re.DOTALL)
_PHASE_A = "Phase A: "
_PATH = re.compile(r"^(?P<path>[a-z_]+(?:\[\d+\])*(?:\.[a-z_]+(?:\[\d+\])*)*): (?P<rest>.*)$", re.DOTALL)
_INDEX = re.compile(r"\[\d+\]")
_QUOTED = r"(?P<q>['\"])(?P<name>.+?)(?P=q)"
# A message must not look technical: an index such as [1], a snake_case or dotted field name, or an
# evidence id such as S10.
_LEAK = re.compile(r"\[\d+\]|\b[a-z]+(?:_[a-z]+)+\b|\b[a-z]+\.[a-z_]+\b|\bS\d+\b")


@dataclass(frozen=True)
class _Parsed:
    stage: str | None
    path: str | None
    reason: str
    noun: str


Template = str | Callable[[re.Match[str], _Parsed], str]


@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    code: str
    severity: str
    template: Template
    path: re.Pattern[str] | None = None
    stage: str | None = None


def _rule(pattern: str, code: str, severity: str, template: Template, *, path: str | None = None, stage: str | None = None) -> _Rule:
    return _Rule(re.compile(pattern, re.DOTALL), code, severity, template, re.compile(path) if path else None, stage)


def _plural(count: str, one: str, many: str) -> str:
    return one if count == "1" else many


def _clean_name(raw: str | None, default: str) -> str:
    name = " ".join((raw or "").split())
    if not name or len(name) > NAME_MAX or _LEAK.search(name):
        return default
    return name


def _removed(match: re.Match[str], _: _Parsed) -> str:
    why = REMOVAL_REASONS.get(match.group("why").strip(), DEFAULT_REMOVAL_REASON)
    return f"{_clean_name(match.group('name'), 'One competitor')} was removed because {why}."


def _dropped_candidate(match: re.Match[str], _: _Parsed) -> str:
    why_text = match.group("why").strip()
    limit = re.fullmatch(r"only (\d+) candidates are kept", why_text)
    why = f"only {limit.group(1)} possible competitors are searched" if limit else REMOVAL_REASONS.get(
        why_text, DEFAULT_REMOVAL_REASON
    )
    return f"{_clean_name(match.group('name'), 'One possible competitor')} was not searched further because {why}."


def _merged(match: re.Match[str], _: _Parsed) -> str:
    into = _clean_name(match.group("into"), "")
    return f"Two entries for {into} were merged into one." if into else "Two entries for the same competitor were merged into one."


def _dropped_count(match: re.Match[str], _: _Parsed) -> str:
    n = match.group("n")
    if n == "1":
        return "1 search result was not counted as a competitor because its type or relevance was unclear."
    return f"{n} search results were not counted as competitors because their type or relevance was unclear."


def _cells(match: re.Match[str], _: _Parsed) -> str:
    n = match.group("n")
    cells = _plural(n, "comparison cell was", "comparison cells were")
    return f"{n} {cells} changed to Unclear because no source names the competitor."


def _verbatim(match: re.Match[str], _: _Parsed) -> str:
    return match.group(0)


# Checked in order; the first match wins. The three spec rewrites (Section 6.7) come first.
RULES: tuple[_Rule, ...] = (
    _rule(r"adds a conclusion .*so it is now an AI interpretation", "claim_overreach", INFO,
          "One {noun} went further than its sources say, so it is marked as an AI interpretation."),
    _rule(r"does not appear with the same magnitude and unit in its cited sources, so it needs verification",
          "figure_unmatched", INFO,
          "A market figure could not be matched to its source text. Treat it as an estimate and verify it."),
    _rule(r"is not about the problem this idea solves", "off_topic_removed", INFO,
          "One {noun} was removed because it was not about the problem your idea solves."),
    _rule(r"does not appear with the same magnitude and unit in its cited sources, so it is now an AI interpretation",
          "figure_unmatched", INFO,
          "One {noun} quoted a figure its sources do not state, so it is marked as an AI interpretation."),
    _rule(r"could not be read reliably, so it is now an AI interpretation", "figure_unclear", INFO,
          "A figure in one {noun} could not be read reliably, so it is marked as an AI interpretation."),
    _rule(r"could not be read reliably, so it needs verification", "figure_unclear", INFO,
          "A market figure could not be read reliably. Treat it as an estimate and verify it."),
    _rule(r"a sourced claim had no valid source", "claim_relabelled", INFO,
          "One {noun} cited no usable source, so it is marked as an AI interpretation."),
    _rule(r"^removed (?:strength|weakness) .*; it had no valid source$", "claim_removed", INFO,
          "One {noun} was removed because no source supports it."),
    _rule(r"^removed ", "website_removed", INFO,
          "A competitor website was removed because the sources do not confirm it.", path=r"website$"),
    _rule(r"^removed website ", "website_removed", INFO,
          "A competitor website was removed because the sources do not confirm it."),
    _rule(r"^replaced an empty website with null", "website_removed", INFO, "An empty competitor website was cleared."),
    _rule(r"^dropped candidate " + _QUOTED + r": (?P<why>.+)$", "candidate_dropped", INFO, _dropped_candidate),
    _rule(r"^removed " + _QUOTED + r"; (?P<why>.+)$", "competitor_removed", INFO, _removed),
    _rule(r"the pricing does not appear in its cited sources, so it needs verification", "price_unmatched", INFO,
          "One competitor price could not be matched to its source text. Treat it as an estimate and verify it."),
    _rule(r"^dropped (?P<n>\d+) with no type or relevance note", "competitor_dropped", INFO, _dropped_count),
    _rule(r"^merged a duplicate (?P<q>['\"])(?P<name>.+?)(?P=q) into (?P<q2>['\"])(?P<into>.+?)(?P=q2)",
          "competitor_merged", INFO, _merged),
    _rule(r"^(?P<n>\d+) cell\(s\) marked evidence_found had no cited source naming the competitor", "cells_unclear",
          INFO, _cells),
    _rule(r"^removed related features that are not in the comparison", "gap_adjusted", INFO,
          "One possible gap pointed to features outside the comparison, so those links were removed."),
    _rule(r"^removed; the comparison shows evidence for its features at most competitors", "gap_removed", INFO,
          "One possible gap was removed because most competitors already show those features."),
    _rule(r"confidence lowered from high to medium", "gap_adjusted", INFO,
          "One possible gap was set to medium confidence, because a gap is only a hypothesis."),
    _rule(r"figure rests only on the search summary, so it needs verification", "figure_unverified", INFO,
          "A market figure rests only on the search summary. Treat it as an estimate and verify it."),
    _rule(r"figure marked sourced cited no valid source, so it is now unavailable", "figure_removed", INFO,
          "A market figure cited no usable source, so it is shown as unavailable."),
    _rule(r"estimated figure cited no evidence, so it is now unavailable", "figure_removed", INFO,
          "An estimated figure cited no evidence, so it is shown as unavailable."),
    _rule(r"removed a figure from an item marked unavailable", "figure_removed", INFO,
          "A figure was removed from an item marked as unavailable."),
    _rule(r"marked sourced but had no figure, so it is unavailable", "figure_removed", INFO,
          "A market size marked as sourced had no figure, so it is shown as unavailable."),
    _rule(r"so it was moved to broader_markets and the (?P<label>TAM|SAM|SOM) is unavailable", "figure_moved", INFO,
          "A {label} figure measured a wider market, so it is listed under broader markets and the {label} is "
          "shown as unavailable."),
    _rule(r"^removed an entry with no figure", "figure_removed", INFO, "A broader-market entry with no figure was removed."),
    _rule(r"listed as a broader market but marked idea_market", "figure_moved", INFO,
          "A broader-market figure stays listed as context only."),
    _rule(r"^removed unknown source id", "citation_removed", INFO, "A citation to a source that does not exist was removed."),
    _rule(r"link\(s\) that are not in the search evidence", "link_removed", INFO,
          "A link that is not in the search results was removed."),
    _rule(r"cannot be listed as a source", "citation_removed", INFO,
          "The search summary was removed from a source list, because it is not a primary source."),
    _rule(r"does not match any segment", "priority_removed", INFO,
          "No priority segment is shown, because the suggested one did not match any segment.", path=r"^priority_segment$"),
    _rule(r"lowered from strong to limited because no market size", "evidence_lowered", INFO,
          "The market evidence rating was lowered to limited, because no source confirms a market size for this "
          "idea's own market.", path=r"^data_quality$"),
    _rule(r"lowered to limited; no competitor came from the search results", "evidence_lowered", INFO,
          "The competitor evidence rating was lowered to limited, because no competitor came from the search "
          "results.", path=r"^data_quality$"),
    _rule(r"^Sources give different figures", "figures_conflict", INFO,
          "Sources give different figures for the same measure. Check the sources before using either.",
          path=r"^data_quality$"),
    _rule(r"^Only \d+ usable search (?:result was|results were) found, so the evidence is limited\.$", "few_sources",
          WARNING, _verbatim),
    _rule(r"^skipped because the web search did not complete", "stage_skipped", WARNING,
          "{stage} was skipped because the web search did not finish."),
    _rule(r"^skipped because the web search found no usable results", "stage_skipped", WARNING,
          "{stage} was skipped because the web search found no usable results."),
    _rule(r"^skipped because the request reached its time limit", "time_limit", WARNING,
          "{stage} was skipped because the run reached its time limit."),
    _rule(r"^skipped because the run was cancelled", CODE_CANCELLED, WARNING,
          "{stage} was skipped because the run was cancelled."),
    _rule(r"^(?P<n>\d+) of (?P<m>\d+) web searches failed, so some sections are empty\.$", "search_failed", WARNING,
          "{n} of {m} web searches failed, so some research sections are empty.", stage=STAGE_SEARCH),
    _rule(r"^Market and competitor research is not available", "research_unavailable", WARNING,
          "Market and competitor research is not available, so only the structured idea is shown.", stage=STAGE_SEARCH),
    _rule(r"^(?P<n>\d+) of (?P<m>\d+) targeted market-size searches failed", "search_failed", WARNING,
          "{n} of {m} market-size searches failed, so fewer market-size results were used."),
    _rule(r"^the targeted market-size searches found no results", "search_empty", WARNING,
          "The market-size searches found no results, so only the main search results were used."),
    _rule(r"^the targeted market-size searches failed", "search_failed", WARNING,
          "The market-size searches failed, so only the main search results were used."),
    _rule(r"^the targeted search .* found no results$", "search_empty", WARNING, "One competitor search found no results."),
    _rule(r"^the targeted search .* failed", "search_failed", WARNING,
          "One competitor search failed, so the analysis used the other results."),
    _rule(r"^all (?P<n>\d+) targeted competitor searches failed", "search_failed", WARNING,
          "All {n} competitor searches failed, so only the main search results were used."),
    _rule(r"^the candidate search failed", "candidates_failed", WARNING,
          "Competitor names could not be listed from the first search, so only general competitor searches were run."),
)


# --- Milestone 3: the strategy stages (MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md 11.3 and 11.4) ---
# Read only under a strategy stage's label. A code's message is built from every warning of that
# code in the stage, so one notice adds up their counts.


@dataclass(frozen=True)
class _StrategyRule:
    pattern: re.Pattern[str]
    code: str
    severity: str
    missing: str | None = None


def _strategy_rule(pattern: str, code: str, severity: str, *, missing: str | None = None) -> _StrategyRule:
    return _StrategyRule(re.compile(pattern, re.DOTALL), code, severity, missing)


STRATEGY_RULES: tuple[_StrategyRule, ...] = (
    _strategy_rule(r"^removed (?P<n>\d+) links? to (?:findings that are not in the digest|risks that are not in the "
                   r"risk analysis|features that are not in the MVP recommendation)\b", REF_REMOVED, INFO),
    _strategy_rule(r"^basis changed: (?:(?P<n>\d+) points? without an existing finding now marked as assumptions)?"
                   r"(?:; )?(?:(?P<m>\d+) points? attributed to the founder\b.*)?$", BASIS_ADJUSTED, INFO),
    _strategy_rule(r"^removed (?P<n>\d+) points? that stated a figure no cited finding contains", FIGURE_REMOVED, WARNING),
    _strategy_rule(r"^removed (?P<n>\d+) points? that promised an outcome", OVERCLAIM_REMOVED, WARNING),
    _strategy_rule(r"^removed (?P<n>\d+) points? that repeated an earlier point", DUPLICATE_REMOVED, INFO),
    _strategy_rule(r"^cut points beyond the list limits \((?P<cut>.+)\)$", ITEMS_CUT, INFO),
    _strategy_rule(r"^shortened (?P<n>\d+) texts? over the length limit", TEXT_SHORTENED, INFO),
    _strategy_rule(r"^skipped because it needs at least one finished analysis", CODE_STRATEGY_SKIPPED, WARNING),
    _strategy_rule(r"^Risks were not considered when (?:choosing features|planning go-to-market)\.$",
                   CODE_INPUTS_MISSING, WARNING, missing="swot"),
    _strategy_rule(r"^The plan is not tied to a feature set because no MVP recommendation was available\.$",
                   CODE_INPUTS_MISSING, WARNING, missing="mvp"),
    _strategy_rule(r"^assumed (?P<parts>.+) because they were not given$", CODE_CONSTRAINTS_ASSUMED, INFO),
    _strategy_rule(r"^the essential features need [\d.]+ person-months but the team has", CODE_OVER_CAPACITY, WARNING),
    _strategy_rule(r"^(?P<n>\d+) channels? may be above a bootstrapped budget", CODE_BUDGET_CONFLICT, INFO),
    _strategy_rule(r"^No customer segments were available, so the positioning is built on the founder's stated customers",
                   CODE_SEGMENTS_MISSING, INFO),
)
INPUTS_RULE = _StrategyRule(re.compile(r"(?!)"), CODE_INPUTS_MISSING, WARNING)
ASSUMED_NAMES = (("team size", r"\ba team of \d+ people\b"), ("timeline", r"\b\d+ months to the first release\b"))

StrategyMessage = Callable[[list[re.Match[str]], list[str]], str]


def _counted(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _total(matches: list[re.Match[str]], name: str = "n") -> int:
    return sum(int(match.group(name)) for match in matches if match.group(name))


def _and(parts: Sequence[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" and {parts[-1]}"


def _basis_message(matches: list[re.Match[str]], _: list[str]) -> str:
    assumed, founder = _total(matches, "n"), _total(matches, "m")
    parts = []
    if assumed:
        parts.append("1 point has no supporting finding, so it is marked as an assumption" if assumed == 1 else
                     f"{assumed} points have no supporting finding, so they are marked as assumptions")
    if founder:
        parts.append("1 point said to come from you is not in your idea or resources, so it is marked as an AI "
                     "interpretation" if founder == 1 else
                     f"{founder} points said to come from you are not in your idea or resources, so they are marked as "
                     "AI interpretations")
    return ". ".join(parts)


def _removed_message(reason: str) -> StrategyMessage:
    def message(matches: list[re.Match[str]], _: list[str]) -> str:
        count = _total(matches)
        return f"{_counted(count, 'point was', 'points were')} removed because {'it' if count == 1 else 'they'} {reason}"
    return message


def _cut_message(matches: list[re.Match[str]], _: list[str]) -> str:
    count = sum(int(number) for match in matches for number in re.findall(r"(\d+)(?=,|$)", match.group("cut")))
    return f"{_counted(count, 'point', 'points')} beyond the list limits {'was' if count == 1 else 'were'} left out"


def _shortened_message(matches: list[re.Match[str]], _: list[str]) -> str:
    count = _total(matches)
    if count == 1:
        return "1 text was shortened to fit its length limit"
    return f"{count} texts were shortened to fit their length limits"


def _inputs_message(_: list[re.Match[str]], inputs: list[str]) -> str:
    names = [name for key, name in INPUT_NAMES.items() if key in inputs]
    return f"This part was written without {_and(names)} because {'it' if len(names) == 1 else 'they'} did not finish"


def _assumed_message(matches: list[re.Match[str]], _: list[str]) -> str:
    parts = matches[-1].group("parts")
    given = [name for name, pattern in ASSUMED_NAMES if re.search(pattern, parts)]
    if not given:
        return f"Some resources were not given, so the plan assumes {parts}"
    return f"Your {_and(given)} {'was' if len(given) == 1 else 'were'} not given, so the plan assumes {parts}"


def _fixed(text: str) -> StrategyMessage:
    return lambda _matches, _inputs: text


STRATEGY_MESSAGES: dict[str, StrategyMessage] = {
    REF_REMOVED: _fixed("Some points were linked to findings that do not exist, so the links were removed."),
    BASIS_ADJUSTED: _basis_message,
    FIGURE_REMOVED: _removed_message("quoted a number that no source states"),
    OVERCLAIM_REMOVED: _removed_message("promised an outcome"),
    DUPLICATE_REMOVED: _fixed("Repeated points were merged."),
    ITEMS_CUT: _cut_message,
    TEXT_SHORTENED: _shortened_message,
    CODE_STRATEGY_SKIPPED: _fixed("This part was skipped because no analysis was available to build on."),
    CODE_INPUTS_MISSING: _inputs_message,
    CODE_CONSTRAINTS_ASSUMED: _assumed_message,
    CODE_OVER_CAPACITY: _fixed(
        "The essential features need more effort than your team and time allow. Narrow the idea or allow more time."
    ),
    CODE_BUDGET_CONFLICT: _fixed("Some channels may cost more than a bootstrapped budget."),
    CODE_SEGMENTS_MISSING: _fixed(
        "No customer segments were available, so the positioning is built on your stated customers and marked as an "
        "assumption."
    ),
}


@dataclass
class _Group:
    stage: str
    notice: Notice
    rule: _StrategyRule | None
    matches: list[re.Match[str]] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _noun(path: str | None) -> str:
    if not path:
        return DEFAULT_NOUN
    for part in reversed(_INDEX.sub("", path).split(".")):
        if part in NOUNS:
            return NOUNS[part]
    return DEFAULT_NOUN


def _parse(warning: str) -> _Parsed:
    text = " ".join(warning.split())
    stage = None
    prefix = _PREFIX.match(text)
    if prefix:
        stage, text = WARNING_LABELS[prefix.group("label")], prefix.group("rest")
    if text.startswith(_PHASE_A):
        text = text[len(_PHASE_A):]
    path = None
    found = _PATH.match(text)
    if found:
        path, text = found.group("path"), found.group("rest")
    return _Parsed(stage=stage, path=path, reason=text, noun=_noun(path))


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return text
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _fallback(stage: str | None) -> str:
    area = {**AREAS, **STRATEGY_AREAS}.get(stage, "the results")
    return f"A quality check adjusted part of {area}. Open the details to see what changed."


def leaks(message: str) -> bool:
    """True when a message looks technical: an index, a field name or an evidence id."""
    return bool(_LEAK.search(message))


def _strategy_match(parsed: _Parsed) -> tuple[_StrategyRule, re.Match[str]] | None:
    if parsed.stage not in STRATEGY_TITLES:
        return None
    for rule in STRATEGY_RULES:
        match = rule.pattern.search(parsed.reason)
        if match is not None:
            return rule, match
    return None


def _strategy_notice(
    stage: str, rule: _StrategyRule, matches: list[re.Match[str]], inputs: list[str], details: list[str]
) -> Notice:
    detail = "\n".join(details) or None
    message = _sentence(STRATEGY_MESSAGES[rule.code](matches, inputs))
    if leaks(message):
        return Notice(stage=stage, code=CODE_FALLBACK, severity=INFO, message=_fallback(stage), detail=detail)
    return Notice(stage=stage, code=rule.code, severity=rule.severity, message=message, detail=detail)


def notice_for_warning(warning: str) -> Notice:
    parsed = _parse(warning)
    found = _strategy_match(parsed)
    if found is not None:
        rule, match = found
        return _strategy_notice(parsed.stage, rule, [match], [rule.missing] if rule.missing else [], [warning])
    for rule in RULES:
        if rule.path is not None and not (parsed.path and rule.path.search(parsed.path)):
            continue
        match = rule.pattern.search(parsed.reason)
        if match is None:
            continue
        stage = parsed.stage or rule.stage
        if callable(rule.template):
            message = rule.template(match, parsed)
        else:
            groups = {key: value for key, value in match.groupdict().items() if value is not None}
            message = rule.template.format(
                **groups, noun=parsed.noun, stage=TITLES.get(stage or "", "This step")
            )
        message = _sentence(message)
        if leaks(message):
            break
        return Notice(stage=stage, code=rule.code, severity=rule.severity, message=message, detail=warning)
    return Notice(stage=parsed.stage, code=CODE_FALLBACK, severity=INFO, message=_fallback(parsed.stage), detail=warning)


def notice_for_error(error: StageError) -> Notice:
    title = TITLES.get(error.stage, "One step")
    message = _sentence(f"{title} did not finish. {error.message}")
    if leaks(message):
        message = f"{title} did not finish. Open the details to see why."
    severity = WARNING if error.code == CODE_CANCELLED else ERROR
    return Notice(
        stage=error.stage, code=error.code, severity=severity, message=message, detail=f"{error.code}: {error.message}"
    )


def _finished(group: _Group) -> Notice:
    if group.rule is None:
        return group.notice.model_copy(update={"detail": "\n".join(group.details)})
    return _strategy_notice(group.stage, group.rule, group.matches, group.inputs, group.details)


def build_notices(
    warnings: list[str], errors: list[StageError], inputs_missing: Mapping[str, Sequence[str]] | None = None
) -> list[Notice]:
    """Stage errors first, then every warning in the order it was raised. Nothing is dropped, so a
    count of notices is a count of the quality checks that changed the result.

    Milestone 3 (Section 11.4): a strategy stage gets one notice per code instead, which adds up the
    counts of its warnings with that code and keeps all of them in `detail`. `inputs_missing` names,
    per strategy stage, the inputs its result was written without (its quality block)."""
    notices: list[Notice | _Group] = [notice_for_error(error) for error in errors]
    groups: dict[tuple[str, str], _Group] = {}

    def group_for(stage: str, notice: Notice, rule: _StrategyRule | None) -> _Group:
        key = (stage, notice.code)
        if key not in groups:
            groups[key] = _Group(stage=stage, notice=notice, rule=rule)
            notices.append(groups[key])
        return groups[key]

    for warning in warnings:
        parsed = _parse(warning)
        notice = notice_for_warning(warning)
        if parsed.stage not in STRATEGY_TITLES:
            notices.append(notice)
            continue
        found = _strategy_match(parsed)
        rule = found[0] if found is not None and found[0].code == notice.code else None
        group = group_for(parsed.stage, notice, rule)
        if rule is not None:
            group.matches.append(found[1])
            group.inputs += [rule.missing] if rule.missing else []
        group.details.append(warning)
    for stage, inputs in (inputs_missing or {}).items():
        names = [name for name in inputs if name in INPUT_NAMES]
        if stage not in STRATEGY_TITLES or not names:
            continue
        group = group_for(stage, _strategy_notice(stage, INPUTS_RULE, [], names, []), INPUTS_RULE)
        group.inputs += names
        group.details.append(f"inputs missing: {', '.join(names)}")
    return [_finished(item) if isinstance(item, _Group) else item for item in notices]
