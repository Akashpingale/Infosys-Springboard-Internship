"""Web Search Agent: turns an extracted idea into live market and competitor research."""

import logging
import re
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from functools import partial
from typing import Any, Callable

from agents.evidence import diverse_results
from agents.query_profile import (
    DIVERSE_EVIDENCE,
    NEWS_SEARCH,
    NEWS_TOPIC,
    QUERY_TERMS,
    REGION_AND_YEAR,
    SEARCH_TERMS,
    current_year,
    uses,
)
from config import DEFAULT_QUERY_PROFILE, get_settings
from models.schemas import SNIPPET_MAX, ExtractedIdea, SearchBundle, SearchResult, SearchSection
from utils.deadline import stop_requested, time_left
from utils.errors import RunCancelledError, SearchAPIError, SearchError
from utils.search_client import DEFAULT_DEPTH, DEFAULT_MAX_RESULTS, MSG_RATE_LIMIT, search

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 120
SHORT_PHRASE_WORDS = 8

MSG_NO_RESULTS = "No live results found for this query."
MSG_ALL_QUERIES_FAILED = "Web search could not be completed. Please try again."

LABEL_MARKET = "Market size and trends"
LABEL_COMPETITORS = "Competitors"
LABEL_DEMAND = "Customer demand and pain points"
LABEL_NEWS = "Recent news and funding"

_NOISE = re.compile(r"[^0-9A-Za-z&+/\- ]+")
RATE_LIMIT_PAUSE_S = 1.0
pause = time.sleep


def _tidy(text: str, *, words: int | None = None) -> str:
    """Drop punctuation noise, collapse whitespace and optionally keep the first words."""
    cleaned = " ".join(_NOISE.sub(" ", text).split())
    if words is not None:
        cleaned = " ".join(cleaned.split()[:words])
    return cleaned


def _trim(query: str) -> str:
    """Cut to MAX_QUERY_CHARS on a word boundary."""
    if len(query) <= MAX_QUERY_CHARS:
        return query
    return query[:MAX_QUERY_CHARS].rsplit(" ", 1)[0]


def search_terms_text(idea: ExtractedIdea) -> str:
    terms = getattr(idea, "search_terms", None) or []
    return " ".join(_tidy(term, words=SHORT_PHRASE_WORDS) for term in terms[:QUERY_TERMS]).strip()


def fit_query(base: str, suffix: str) -> str:
    base, suffix = " ".join(base.split()), " ".join(suffix.split())
    if not suffix:
        return _trim(base)
    room = MAX_QUERY_CHARS - len(suffix) - 1
    head = base if len(base) <= room else base[: max(room, 0)].rsplit(" ", 1)[0]
    return _trim(f"{head} {suffix}".strip())


def generate_queries(
    idea: ExtractedIdea, *, profile: str = DEFAULT_QUERY_PROFILE, region: str | None = None
) -> list[tuple[str, str]]:
    """Build four distinct search queries from templates. No LLM call, so it is cheap
    and deterministic."""
    industry = _tidy(idea.industry, words=SHORT_PHRASE_WORDS)
    solution = _tidy(idea.solution, words=SHORT_PHRASE_WORDS)
    problem = _tidy(idea.problem, words=SHORT_PHRASE_WORDS)
    customer = _tidy(idea.target_customers[0], words=SHORT_PHRASE_WORDS)

    if uses(profile, SEARCH_TERMS):
        terms = search_terms_text(idea)
        templates = [
            (LABEL_MARKET, f"{terms or f'{industry} {solution}'} market size and growth"),
            (LABEL_COMPETITORS, f"{terms or problem} competitors and alternatives"),
            (LABEL_DEMAND, f"{terms or f'{customer} {problem}'} customer problems and demand"),
            (LABEL_NEWS, f"{terms or industry} funding and news"),
        ]
    else:
        templates = [
            (LABEL_MARKET, f"{industry} {solution} market size growth trends"),
            (LABEL_COMPETITORS, f"{problem} competitors alternatives startups"),
            (LABEL_DEMAND, f"{customer} {problem} demand pain points"),
            (LABEL_NEWS, f"{industry} startups funding news recent"),
        ]
    if uses(profile, REGION_AND_YEAR):
        place, year = _tidy(region or "", words=SHORT_PHRASE_WORDS), str(current_year())
        added = {LABEL_MARKET: f"{place} {year}", LABEL_COMPETITORS: place, LABEL_DEMAND: place, LABEL_NEWS: year}
        return [(label, fit_query(query, added[label])) for label, query in templates]
    return [(label, _trim(" ".join(query.split()))) for label, query in templates]


def query_options(profile: str = DEFAULT_QUERY_PROFILE) -> dict[str, dict[str, str]]:
    return {LABEL_NEWS: dict(NEWS_SEARCH)} if uses(profile, NEWS_TOPIC) else {}


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= SNIPPET_MAX:
        return text
    return text[: SNIPPET_MAX - 3].rstrip() + "..."


def _focus(builder: Callable[[str, str], str], query: str, content: str) -> str:
    """A caller's snippet for this query, or the default one if it is empty or too long."""
    chosen = " ".join(builder(content, query).split())
    return chosen if chosen and len(chosen) <= SNIPPET_MAX else _snippet(content)


def _score(raw: Any) -> float | None:
    return raw if isinstance(raw, (int, float)) and 0 <= raw <= 1 else None


def _normalize(
    raw_results: Any, seen_urls: set[str], make_snippet: Callable[[str], str] = _snippet
) -> list[SearchResult]:
    """Keep results that have both a URL and content, drop URLs already shown."""
    results = []
    for item in raw_results if isinstance(raw_results, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if not url or not content or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            SearchResult(
                title=str(item.get("title") or "").strip() or url,
                url=url,
                snippet=make_snippet(content),
                score=_score(item.get("score")),
            )
        )
    return results


def _answer(raw: Any) -> str | None:
    text = " ".join(str(raw).split()) if raw else ""
    return text or None


def run_web_search(idea: ExtractedIdea, *, region: str | None = None) -> SearchBundle:
    """Run the four template queries for an idea and collect the results."""
    profile = get_settings().query_profile
    if profile == DEFAULT_QUERY_PROFILE:
        return run_queries(generate_queries(idea))
    return run_queries(generate_queries(idea, profile=profile, region=region), options=query_options(profile))


Outcome = tuple[dict[str, Any] | None, Exception | None]


def _fetch(query: str, extra: Mapping[str, str], max_results: int, depth: str) -> Outcome:
    try:
        return search(query, max_results=max_results, depth=depth, include_answer=True, **extra), None
    except SearchError as exc:
        return None, exc


def _rate_limited(outcome: Outcome) -> bool:
    problem = outcome[1]
    return isinstance(problem, SearchAPIError) and problem.user_message == MSG_RATE_LIMIT


def _settle(running: dict[Future, int], outcomes: list[Outcome | None], *, block: bool) -> bool:
    done = wait(list(running), return_when=FIRST_COMPLETED)[0] if block else {f for f in running if f.done()}
    limited = False
    for future in done:
        index = running.pop(future)
        problem = future.exception()
        outcomes[index] = (None, problem) if problem is not None else future.result()
        limited = limited or _rate_limited(outcomes[index])
    return limited


def _pause_for_rate_limit() -> None:
    left = time_left()
    seconds = RATE_LIMIT_PAUSE_S if left is None else min(RATE_LIMIT_PAUSE_S, max(left, 0.0))
    if seconds > 0:
        pause(seconds)


def _broken(outcomes: list[Outcome | None]) -> bool:
    return any(o is not None and o[1] is not None and not isinstance(o[1], SearchError) for o in outcomes)


def _parallel_outcomes(calls: list[Callable[[], Outcome]], workers: int) -> list[Outcome]:
    outcomes: list[Outcome | None] = [None] * len(calls)
    running: dict[Future, int] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, call in enumerate(calls):
            limited = _settle(running, outcomes, block=False)
            while len(running) >= workers:
                limited = _settle(running, outcomes, block=True) or limited
            if limited:
                _pause_for_rate_limit()
            if _broken(outcomes) or stop_requested():
                break
            left = time_left()
            if left is not None and left <= 0:
                outcomes[index] = call()
                continue
            running[pool.submit(copy_context().run, call)] = index
        while running:
            _settle(running, outcomes, block=True)
    return [(None, RunCancelledError()) if outcome is None else outcome for outcome in outcomes]


def _outcomes(calls: list[Callable[[], Outcome]]) -> list[Outcome]:
    workers = get_settings().search_max_parallel
    if workers <= 1 or len(calls) <= 1:
        return [call() for call in calls]
    return _parallel_outcomes(calls, workers)


def run_queries(
    queries: list[tuple[str, str]],
    *,
    max_results: int | None = None,
    depth: str | None = None,
    snippet: Callable[[str, str], str] | None = None,
    options: Mapping[str, Mapping[str, str]] | None = None,
) -> SearchBundle:
    """Run any list of (label, query) pairs and return one normalised, de-duplicated bundle.

    A query that fails records its message in its own section and the others continue.
    If every query fails, SearchAPIError is raised because there is nothing to show.
    `snippet(content, query)` may choose what part of each result's content becomes its snippet
    (at most SNIPPET_MAX characters); by default it is the first characters, as in Milestone 1.
    """
    started = time.perf_counter()
    sections: list[SearchSection] = []
    seen_urls: set[str] = set()
    queries_failed = 0
    count = DEFAULT_MAX_RESULTS if max_results is None else max_results
    level = DEFAULT_DEPTH if depth is None else depth
    calls = [partial(_fetch, query, (options or {}).get(label, {}), count, level) for label, query in queries]

    entries: list[tuple[str, str, Outcome, list[SearchResult]]] = []
    for (label, query), outcome in zip(queries, _outcomes(calls)):
        body, problem = outcome
        if problem is not None and not isinstance(problem, SearchError):
            raise problem
        make_snippet = _snippet if snippet is None else partial(_focus, snippet, query)
        results = [] if body is None else _normalize(body.get("results"), seen_urls, make_snippet)
        entries.append((label, query, outcome, results))

    if uses(get_settings().query_profile, DIVERSE_EVIDENCE):
        kept = diverse_results([results for *_, results in entries])
        entries = [(*entry[:3], results) for entry, results in zip(entries, kept)]

    for label, query, (body, problem), results in entries:
        if body is None:
            queries_failed += 1
            sections.append(SearchSection(label=label, query=query, error=problem.user_message))
            continue
        sections.append(
            SearchSection(
                label=label,
                query=query,
                answer=_answer(body.get("answer")),
                results=results,
                error=None if results else MSG_NO_RESULTS,
            )
        )

    if sections and queries_failed == len(sections):
        logger.warning("all %d search queries failed", queries_failed)
        raise SearchAPIError(MSG_ALL_QUERIES_FAILED)

    total_results = sum(len(section.results) for section in sections)
    logger.info(
        "web search done in %.2fs (%d results, %d of %d queries failed)",
        time.perf_counter() - started,
        total_results,
        queries_failed,
        len(sections),
    )
    return SearchBundle(
        sections=sections, total_results=total_results, queries_failed=queries_failed
    )


def render_markdown(bundle: SearchBundle) -> str:
    """One readable report format, shared by the UI and the test report."""
    lines = ["# Market and competitor research", ""]
    for section in bundle.sections:
        lines += [f"## {section.label}", f"Query: {section.query}", ""]
        if section.error:
            lines += [f"Note: {section.error}", ""]
        if section.answer:
            lines += [f"Summary: {section.answer}", ""]
        for number, result in enumerate(section.results, 1):
            lines += [f"{number}. {result.title}", f"   {result.url}", f"   {result.snippet}", ""]
    lines += [
        f"Total results: {bundle.total_results}",
        f"Queries failed: {bundle.queries_failed}",
    ]
    return "\n".join(lines)
