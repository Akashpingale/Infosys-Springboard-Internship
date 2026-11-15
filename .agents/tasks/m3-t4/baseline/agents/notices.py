"""Plain-language quality notes (KIRO_UI_UPGRADE_SPEC.md Sections 6.7 and 10.3).

The agents and the orchestrator write `warnings` in technical terms, often starting with the field
they repaired ("market_demand.demand_evidence[1]: ..."). Those stay unchanged in PipelineResult.
`build_notices` turns each stage error and each warning into a Notice whose `message` is plain and
never names a field, an index or an evidence id; the original text is kept in `detail`. Wording
this module does not know gets a general message, so a new warning can never leak a field path.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from agents.competitor_analysis_agent import STAGE_COMPETITOR
from agents.competitor_analysis_agent import WARNING_PREFIX as COMPETITOR_PREFIX
from agents.market_opportunity_agent import STAGE_MARKET
from agents.market_opportunity_agent import WARNING_PREFIX as MARKET_PREFIX
from models.schemas import Notice, StageError

STAGE_EXTRACTION = "extraction"
STAGE_SEARCH = "search"

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
}
AREAS = {
    STAGE_EXTRACTION: "the extracted idea",
    STAGE_SEARCH: "the web search results",
    STAGE_MARKET: "the market analysis",
    STAGE_COMPETITOR: "the competitor analysis",
}

INFO, WARNING, ERROR = "info", "warning", "error"
CODE_FALLBACK = "quality_adjusted"
CODE_CANCELLED = "run_cancelled"

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
    return f"A quality check adjusted part of {AREAS.get(stage, 'the results')}. Open the details to see what changed."


def leaks(message: str) -> bool:
    """True when a message looks technical: an index, a field name or an evidence id."""
    return bool(_LEAK.search(message))


def notice_for_warning(warning: str) -> Notice:
    parsed = _parse(warning)
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
                **groups, noun=parsed.noun, stage=STAGE_TITLES.get(stage or "", "This step")
            )
        message = _sentence(message)
        if leaks(message):
            break
        return Notice(stage=stage, code=rule.code, severity=rule.severity, message=message, detail=warning)
    return Notice(stage=parsed.stage, code=CODE_FALLBACK, severity=INFO, message=_fallback(parsed.stage), detail=warning)


def notice_for_error(error: StageError) -> Notice:
    title = STAGE_TITLES.get(error.stage, "One step")
    message = _sentence(f"{title} did not finish. {error.message}")
    if leaks(message):
        message = f"{title} did not finish. Open the details to see why."
    severity = WARNING if error.code == CODE_CANCELLED else ERROR
    return Notice(
        stage=error.stage, code=error.code, severity=severity, message=message, detail=f"{error.code}: {error.message}"
    )


def build_notices(warnings: list[str], errors: list[StageError]) -> list[Notice]:
    """Stage errors first, then every warning in the order it was raised. Nothing is dropped, so a
    count of notices is a count of the quality checks that changed the result."""
    return [*(notice_for_error(error) for error in errors), *(notice_for_warning(warning) for warning in warnings)]
