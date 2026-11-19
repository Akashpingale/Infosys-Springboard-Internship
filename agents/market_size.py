"""Market size for the Market Opportunity Agent (KIRO_PROMPT_M2.md Task 1).

TAM, SAM and SOM describe this idea's own market only. This module runs two targeted
market-size searches, adds their results to the evidence, and checks every figure:

- its amount must appear, with the same magnitude and unit, in a cited snippet (Section 7.2);
- a TAM, SAM or SOM must be marked `idea_market` and come from a source that names this
  idea's market in the words of its title.

Anything else is moved to `broader_markets` as context, so a figure for a wider market, such as
the whole agritech sector, is never shown as this idea's market size. Code never invents,
derives or rescales a figure.
"""

import re

from agents.evidence import (
    SKIPPED_WORDS,
    build_evidence,
    focused_snippet,
    normalize_url,
    sourced_items,
    text_words,
)
from agents.figures import SUPPORTED, UNCLEAR, check_figure, mentions_amount, singular
from agents.integrity import supporting_source_ids, valid_source_ids
from agents.query_profile import DEEP_SEARCH, MARKET_SIZE_DEPTH, SEARCH_TERMS, uses
from agents.web_search_agent import MAX_QUERY_CHARS, fit_query, run_queries, search_terms_text
from config import DEFAULT_QUERY_PROFILE, get_settings
from models.schemas import (
    MARKET_SCOPES,
    EvidenceItem,
    ExtractedIdea,
    MarketFigure,
    MarketOpportunityResult,
    SearchBundle,
    SearchSection,
)
from utils.errors import SearchError

IDEA_MARKET, BROADER_MARKET = MARKET_SCOPES
FIGURES = ("tam", "sam", "som")
LABELS = {"tam": "TAM", "sam": "SAM", "som": "SOM"}

LABEL_IDEA_MARKET = "Market size for this idea"
LABEL_CUSTOMER_MARKET = "Market size for the target customers"
QUERY_WORDS = 8
# A source names this idea's market when it uses two of the title's market words (or the only one).
MIN_MARKET_TERMS = 2

FIGURE_NOT_FOUND = (
    "the figure does not appear with the same magnitude and unit in its cited sources, so it needs verification"
)
FIGURE_UNCLEAR = "its amount, magnitude or unit could not be read reliably, so it needs verification"
SCOPE_MISSING = "has no market scope, which counts as a broader market"
SCOPE_BROADER = "is marked as a broader market"
SCOPE_NOT_NAMED = "comes from sources that do not name this idea's market"
NOTE_NO_IDEA_MARKET = "No market size for this idea's own market is confirmed by a cited source."
WARNING_LEVEL_CAPPED = (
    "data_quality: the evidence level was lowered from strong to limited because no market size "
    "for this idea's own market is confirmed by a cited source"
)
SHORT_VALUE = 60

_LETTERS = re.compile(r"[^\W\d_]+")
_NOISE = re.compile(r"[^0-9A-Za-z&+/\- ]+")  # the same noise rule as the Milestone 1 queries


# --- what this idea's market is called ------------------------------------------


def _words(text: str | None) -> set[str]:
    return text_words(text)


def market_terms(idea: ExtractedIdea | None) -> frozenset[str]:
    """Words of the idea title that name its market, for example {crop, disease, detection}.

    Generic product words (app, platform, AI), stop words and the words of the industry and
    the target customers are left out, so naming the industry ("agritech") or the customers
    ("farmers in India") is not enough to name this idea's market.
    """
    if idea is None:
        return frozenset()
    context = _words(idea.industry).union(*(_words(customer) for customer in idea.target_customers))
    terms = set()
    for raw in _LETTERS.findall(idea.idea_title.lower()):
        word = singular(raw)
        if len(raw) >= 3 and not {raw, word} & SKIPPED_WORDS and word not in context:
            terms.add(word)
    return frozenset(terms)


def names_market(text: str | None, terms: frozenset[str]) -> bool:
    """True when the text uses enough of the idea's market words: two of them, or the only one."""
    if not terms:
        return False
    return len(_words(text) & terms) >= min(MIN_MARKET_TERMS, len(terms))


# --- targeted searches ------------------------------------------------------------


def _query_text(text: str | None) -> str:
    return " ".join(_NOISE.sub(" ", text or "").split()[:QUERY_WORDS])


def _trim(query: str) -> str:
    return query if len(query) <= MAX_QUERY_CHARS else query[:MAX_QUERY_CHARS].rsplit(" ", 1)[0]


def market_size_queries(
    idea: ExtractedIdea, *, profile: str = DEFAULT_QUERY_PROFILE, region: str | None = None
) -> list[tuple[str, str]]:
    """Two searches aimed at this idea's own market: its title, then its title and its first
    target customer, which often names the region. Built from templates, with no LLM call."""
    title = _query_text(idea.idea_title) or _query_text(idea.industry)
    if uses(profile, SEARCH_TERMS):
        title = search_terms_text(idea) or title
    if uses(profile, MARKET_SIZE_DEPTH):
        place = _query_text(region)
        return [
            (LABEL_IDEA_MARKET, fit_query(f"{title} market size", f"{place} billion")),
            (LABEL_CUSTOMER_MARKET, fit_query(f"{title} number of users or customers", place)),
        ]
    queries = [(LABEL_IDEA_MARKET, f"{title} market size")]
    customer = _query_text(idea.target_customers[0]) if idea.target_customers else ""
    if customer:
        queries.append((LABEL_CUSTOMER_MARKET, f"{title} market size {customer}"))
    return [(label, _trim(query)) for label, query in queries]


def search_market_size(idea: ExtractedIdea, *, region: str | None = None) -> tuple[SearchBundle | None, list[str]]:
    """Run the targeted searches through the shared search function (Section 5.5), with
    snippets that keep whole sentences and their figures (focused_snippet).

    A failure never stops the analysis: it is reported in a warning, and the standard search
    results are used on their own.
    """
    profile = get_settings().query_profile
    queries = market_size_queries(idea, profile=profile, region=region)
    deeper = {"depth": DEEP_SEARCH} if uses(profile, MARKET_SIZE_DEPTH) else {}
    try:
        bundle = run_queries(queries, snippet=focused_snippet, **deeper)
    except SearchError as exc:
        return None, [
            f"the targeted market-size searches failed ({exc.user_message}), "
            "so only the standard search results were used"
        ]
    warnings = []
    if bundle.queries_failed:
        warnings.append(
            f"{bundle.queries_failed} of {len(queries)} targeted market-size searches failed, "
            "so fewer market-size results were used"
        )
    if not bundle.total_results:
        warnings.append(
            "the targeted market-size searches found no results, so only the standard search results were used"
        )
    return bundle, warnings


# --- evidence ---------------------------------------------------------------------------


def _url_key(url: str) -> str:
    return normalize_url(url) or url.strip()


def _split_targeted(
    market_search: SearchBundle | None, terms: frozenset[str], known_urls: set[str]
) -> tuple[list[SearchSection], list[SearchSection]]:
    """Targeted results that name this idea's market, and the others. A result whose page is
    already among the standard results is left out, so no page is listed twice."""
    relevant: list[SearchSection] = []
    other: list[SearchSection] = []
    for section in market_search.sections if market_search else []:
        fresh = [result for result in section.results if _url_key(result.url) not in known_urls]
        hits = [result for result in fresh if names_market(f"{result.title} {result.snippet}", terms)]
        misses = [result for result in fresh if result not in hits]
        for results, group in ((hits, relevant), (misses, other)):
            if results:
                group.append(SearchSection(label=section.label, query=section.query, results=results))
    return relevant, other


def market_evidence(
    search: SearchBundle | None,
    market_search: SearchBundle | None = None,
    idea: ExtractedIdea | None = None,
    max_items: int | None = None,
) -> list[EvidenceItem]:
    """The evidence for the market analysis: the standard results, numbered as build_evidence
    numbers them, then the targeted market-size results.

    Targeted results that name this idea's market are kept ahead of the EVIDENCE_MAX_ITEMS cap:
    room is made for them by keeping fewer standard results. Other targeted results only use
    room that is left. Their search summaries are not added, so S0 stays the standard summary.
    """
    limit = get_settings().evidence_max_items if max_items is None else max(max_items, 0)
    known = {_url_key(result.url) for section in (search.sections if search else []) for result in section.results}
    relevant, other = _split_targeted(market_search, market_terms(idea), known)
    reserved = min(sum(len(section.results) for section in relevant), limit)
    standard = build_evidence(search, max_items=limit - reserved) if search is not None else []
    used = len(sourced_items(standard))
    extra = build_evidence(
        SearchBundle(sections=[*relevant, *other]),
        max_items=limit - used,
        first_number=used + 1,
        include_summary=False,
    )
    return [*standard, *extra]


# --- figure checks ------------------------------------------------------------------


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= SHORT_VALUE else text[: SHORT_VALUE - 3] + "..."


def _has_value(figure: MarketFigure) -> bool:
    return bool((figure.value or "").strip())


def _check_amount(
    figure: MarketFigure, evidence: list[EvidenceItem], label: str
) -> tuple[MarketFigure, list[str]]:
    """Section 7.2: a sourced figure stays sourced only if every amount it states appears, with
    the same magnitude and unit, in a cited snippet other than S0. Otherwise it becomes an
    estimate that keeps its figure unchanged. (repair_tree already made a figure that cites
    nothing valid unavailable.)"""
    if figure.status != "sourced":
        return figure, []
    if not _has_value(figure):
        warning = f"{label}: marked sourced but had no figure, so it is unavailable"
        return figure.model_copy(update={"status": "unavailable", "value": None}), [warning]
    snippets = {item.id.upper(): item.snippet for item in sourced_items(evidence)}
    cited = [snippets[sid] for sid in supporting_source_ids(figure.source_ids, evidence) if sid in snippets]
    verdict = check_figure(figure.value, cited)
    if verdict == SUPPORTED:
        return figure, []
    reason = FIGURE_UNCLEAR if verdict == UNCLEAR else FIGURE_NOT_FOUND
    return figure.model_copy(update={"status": "estimate_needs_verification"}), [f"{label}: {reason}"]


def _cited_items(figure: MarketFigure, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    """The evidence a figure cites: real sources for a sourced figure; for an estimate the
    search summary S0 counts too, as it does in repair_tree."""
    if figure.status == "sourced":
        ids = supporting_source_ids(figure.source_ids, evidence)
    else:
        ids = valid_source_ids(figure.source_ids, evidence)
    by_id = {item.id.upper(): item for item in evidence}
    return [by_id[sid] for sid in ids if sid in by_id]


def _scope_problem(figure: MarketFigure, evidence: list[EvidenceItem], terms: frozenset[str]) -> str | None:
    """Why a TAM, SAM or SOM is not shown to measure this idea's own market, or None when it is.

    It must be marked idea_market, and the cited source that states its amount must name this
    idea's market in its title or snippet. An estimate whose amount no cited source states
    passes when any cited source names the market.
    """
    if figure.scope is None:
        return SCOPE_MISSING
    if figure.scope != IDEA_MARKET:
        return SCOPE_BROADER
    cited = _cited_items(figure, evidence)
    stating = [item for item in cited if mentions_amount(figure.value, item.snippet)]
    checked = stating if stating or figure.status == "sourced" else cited
    if any(names_market(f"{item.title} {item.snippet}", terms) for item in checked):
        return None
    return SCOPE_NOT_NAMED


def _move_broader_figures(
    result: MarketOpportunityResult, evidence: list[EvidenceItem], terms: frozenset[str]
) -> tuple[MarketOpportunityResult, list[MarketFigure], list[str]]:
    """A TAM, SAM or SOM that is not shown to measure this idea's market moves to
    broader_markets unchanged; its slot becomes unavailable with a note saying why."""
    updates: dict[str, MarketFigure] = {}
    moved: list[MarketFigure] = []
    warnings: list[str] = []
    for name in FIGURES:
        figure = getattr(result.market_size, name)
        if not _has_value(figure):
            continue
        problem = _scope_problem(figure, evidence, terms)
        if problem is None:
            continue
        label, value = LABELS[name], _short(figure.value or "")
        moved.append(figure.model_copy(update={"scope": BROADER_MARKET}))
        updates[name] = MarketFigure(
            status="unavailable",
            note=(
                f"No {label} for this idea's own market was found. The figure offered ({value}) "
                f"{problem}, so it is listed under broader_markets."
            ),
        )
        warnings.append(
            f"market_size.{name}: {value} {problem}, so it was moved to broader_markets and the {label} is unavailable"
        )
    if not updates:
        return result, [], []
    size = result.market_size.model_copy(update=updates)
    return result.model_copy(update={"market_size": size}), moved, warnings


def _check_broader_markets(
    figures: list[MarketFigure], evidence: list[EvidenceItem]
) -> tuple[list[MarketFigure], list[str]]:
    """Figures the model listed as broader markets get the same amount check. An entry left
    without a figure is removed, and every entry is marked broader_market."""
    kept: list[MarketFigure] = []
    warnings: list[str] = []
    for index, figure in enumerate(figures):
        label = f"broader_markets[{index}]"
        if not _has_value(figure):
            warnings.append(f"{label}: removed an entry with no figure")
            continue
        figure, found = _check_amount(figure, evidence, label)
        warnings += found
        if figure.scope == IDEA_MARKET:
            warnings.append(f"{label}: listed as a broader market but marked idea_market, so it stays a broader market")
        kept.append(figure.model_copy(update={"scope": BROADER_MARKET}))
    return kept, warnings


def _cap_evidence_level(result: MarketOpportunityResult) -> tuple[MarketOpportunityResult, list[str]]:
    """Without a sourced TAM, SAM or SOM for this idea's own market, the evidence level is at
    most limited, and data_quality says why."""
    size = result.market_size
    if any(getattr(size, name).status == "sourced" for name in FIGURES):
        return result, []
    quality = result.data_quality
    notes = quality.notes if NOTE_NO_IDEA_MARKET in quality.notes else [*quality.notes, NOTE_NO_IDEA_MARKET]
    capped = quality.evidence_level == "strong"
    level = "limited" if capped else quality.evidence_level
    fixed = quality.model_copy(update={"evidence_level": level, "notes": notes})
    return result.model_copy(update={"data_quality": fixed}), [WARNING_LEVEL_CAPPED] if capped else []


def guard_market_size(
    result: MarketOpportunityResult, evidence: list[EvidenceItem], idea: ExtractedIdea | None
) -> tuple[MarketOpportunityResult, list[str]]:
    """Every market-size check, in order: amounts, then scope (moving figures for other
    markets to broader_markets), then the model's own broader_markets, then the evidence-level
    cap. Returns the result and one warning per repair."""
    warnings: list[str] = []
    checked: dict[str, MarketFigure] = {}
    for name in FIGURES:
        checked[name], found = _check_amount(getattr(result.market_size, name), evidence, f"market_size.{name}")
        warnings += found
    result = result.model_copy(update={"market_size": result.market_size.model_copy(update=checked)})
    result, moved, found = _move_broader_figures(result, evidence, market_terms(idea))
    warnings += found
    listed, found = _check_broader_markets(result.broader_markets, evidence)
    warnings += found
    result = result.model_copy(update={"broader_markets": [*moved, *listed]})
    result, found = _cap_evidence_level(result)
    return result, warnings + found
