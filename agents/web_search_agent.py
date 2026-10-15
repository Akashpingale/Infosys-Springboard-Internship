"""Web Search Agent: turns an extracted idea into live market and competitor research."""

import logging
import re
import time
from typing import Any

from models.schemas import SNIPPET_MAX, ExtractedIdea, SearchBundle, SearchResult, SearchSection
from utils.errors import SearchAPIError, SearchError
from utils.search_client import DEFAULT_DEPTH, DEFAULT_MAX_RESULTS, search

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


def generate_queries(idea: ExtractedIdea) -> list[tuple[str, str]]:
    """Build four distinct search queries from templates. No LLM call, so it is cheap
    and deterministic."""
    industry = _tidy(idea.industry, words=SHORT_PHRASE_WORDS)
    solution = _tidy(idea.solution, words=SHORT_PHRASE_WORDS)
    problem = _tidy(idea.problem, words=SHORT_PHRASE_WORDS)
    customer = _tidy(idea.target_customers[0], words=SHORT_PHRASE_WORDS)

    templates = [
        (LABEL_MARKET, f"{industry} {solution} market size growth trends"),
        (LABEL_COMPETITORS, f"{problem} competitors alternatives startups"),
        (LABEL_DEMAND, f"{customer} {problem} demand pain points"),
        (LABEL_NEWS, f"{industry} startups funding news recent"),
    ]
    return [(label, _trim(" ".join(query.split()))) for label, query in templates]


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= SNIPPET_MAX:
        return text
    return text[: SNIPPET_MAX - 3].rstrip() + "..."


def _score(raw: Any) -> float | None:
    return raw if isinstance(raw, (int, float)) and 0 <= raw <= 1 else None


def _normalize(raw_results: Any, seen_urls: set[str]) -> list[SearchResult]:
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
                snippet=_snippet(content),
                score=_score(item.get("score")),
            )
        )
    return results


def _answer(raw: Any) -> str | None:
    text = " ".join(str(raw).split()) if raw else ""
    return text or None


def run_web_search(idea: ExtractedIdea) -> SearchBundle:
    """Run the four queries and collect the results.

    A query that fails records its message in its own section and the others continue.
    If every query fails, SearchAPIError is raised because there is nothing to show.
    """
    started = time.perf_counter()
    sections: list[SearchSection] = []
    seen_urls: set[str] = set()
    queries_failed = 0

    for label, query in generate_queries(idea):
        try:
            body = search(
                query,
                max_results=DEFAULT_MAX_RESULTS,
                depth=DEFAULT_DEPTH,
                include_answer=True,
            )
        except SearchError as exc:
            queries_failed += 1
            sections.append(SearchSection(label=label, query=query, error=exc.user_message))
            continue

        results = _normalize(body.get("results"), seen_urls)
        sections.append(
            SearchSection(
                label=label,
                query=query,
                answer=_answer(body.get("answer")),
                results=results,
                error=None if results else MSG_NO_RESULTS,
            )
        )

    if queries_failed == len(sections):
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
