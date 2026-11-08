"""Claim checks for the Market Opportunity Agent (KIRO_PROMPT_M2.md Task 1).

Code, not the model, checks three things the prompt alone did not secure in the live runs:

- a sourced claim states only what its sources say: one that adds a hedge or conclusion word
  (may, could, likely, suggests...) that none of its cited sources uses is an AI interpretation;
- a customer problem or pain point is about the problem this idea solves: it shares a word with
  the idea's problem, solution, features or title, in its own text or in its cited sources;
- when claims give different counts for the same named product (for example Plantix downloads),
  the data-quality notes say so and list each figure with its sources. No figure is picked or
  changed.

These are word checks, not a reading of meaning, so each one errs towards caution: a claim is
relabelled or noted, and only an off-topic pain point is removed.
"""

import math
import re
from dataclasses import dataclass

from agents.evidence import GENERIC_WORDS
from agents.figures import STOP_WORDS, read, singular
from models.schemas import ExtractedIdea

# Words that turn a reported fact into a conclusion, a guess or a prediction.
INFERENCE_WORDS = {
    "might": "might",
    "could": "could",
    "likely": "likely",
    "unlikely": "likely",
    "possibly": "possibly",
    "potentially": "potentially",
    "perhaps": "perhaps",
    "probably": "probably",
    "suggest": "suggest",
    "suggests": "suggest",
    "suggesting": "suggest",
    "suggested": "suggest",
    "indicate": "indicate",
    "indicates": "indicate",
    "indicating": "indicate",
    "indicated": "indicate",
    "imply": "imply",
    "implies": "imply",
    "implying": "imply",
    "implied": "imply",
}
# "may" counts only in lower case, so the month in "May 2025" is not a hedge.
MAY = "may"

# Words of a problem or solution description that say nothing about which problem it is.
RELEVANCE_GENERIC = frozenset(
    """often face faces facing faced significant lack lacks lacking immediate information lead leads
    leading provide provides providing offer offers offering ensure ensures timely accessible
    accessibility access help helps need needs needed make makes able unable user customer people
    issue problem challenge difficult difficulty high low large small easy better faster local
    support supports multi based many much""".split()
)
_IGNORED = STOP_WORDS | GENERIC_WORDS | RELEVANCE_GENERIC
# A word's root is its first six letters once a plural and a common ending are removed, so
# "diagnosis", "diagnose" and "diagnostic" match, and "intervention" never matches "intermediaries".
ROOT_LENGTH = 6
_ENDINGS = ("ations", "ation", "ments", "ment", "ings", "ing", "ions", "ion", "ed", "er", "ly")
MIN_ROOT = 4
MIN_COUNT = 1000  # smaller counts, such as "37 disease categories", are rarely the same measure

_LETTERS = re.compile(r"[^\W\d_]+")
_WORD = re.compile(r"[A-Za-z]+")
# A product or place name inside a sentence: Plantix, AgriTech. Not AI or CNN.
_NAME = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]*)*\b")
_SENTENCE_END = ".!?:;"


# --- added conclusions ------------------------------------------------------------------


def _inference_words(text: str | None) -> list[str]:
    found = []
    for word in _WORD.findall(text or ""):
        family = MAY if word == MAY else INFERENCE_WORDS.get(word.lower())
        if family and family not in found:
            found.append(family)
    return found


def added_inference(claim: str | None, cited_texts: list[str]) -> str | None:
    """The first hedge or conclusion word the claim uses that none of its cited texts uses."""
    cited = {word for text in cited_texts for word in _inference_words(text)}
    return next((word for word in _inference_words(claim) if word not in cited), None)


# --- relevance to the idea's problem ------------------------------------------------------


def _root(word: str) -> str:
    base = word[:-2] if word.endswith("sses") else singular(word)  # "losses" is "loss"
    for ending in _ENDINGS:
        if base.endswith(ending) and len(base) - len(ending) >= MIN_ROOT:
            base = base[: -len(ending)]
            break
    return base[:ROOT_LENGTH]


def _roots(text: str | None) -> set[str]:
    return {_root(word) for word in _LETTERS.findall((text or "").lower()) if len(word) >= 3}


def problem_terms(idea: ExtractedIdea | None) -> frozenset[str]:
    """Roots of the words that say which problem this idea solves and how: its title, problem,
    solution and key features, without stop words, generic words and the words of its industry
    and target customers (naming the customers is not naming their problem)."""
    if idea is None:
        return frozenset()
    context = set().union(*(_roots(text) for text in (idea.industry, *idea.target_customers)))
    terms = set()
    for text in (idea.idea_title, idea.problem, idea.solution, *idea.key_features):
        for word in _LETTERS.findall(text.lower()):
            if len(word) < 3 or word in _IGNORED or singular(word) in _IGNORED:
                continue
            root = _root(word)
            if root not in context:
                terms.add(root)
    return frozenset(terms)


def about_problem(text: str | None, cited_texts: list[str], terms: frozenset[str]) -> bool:
    """True when the claim or its cited sources use at least one of the idea's problem terms.
    With no terms to compare against, nothing can be judged, so the claim is kept."""
    if not terms:
        return True
    return bool(_roots(" ".join([text or "", *cited_texts])) & terms)


# --- different counts for the same product ------------------------------------------------


@dataclass(frozen=True)
class Claim:
    text: str
    source_ids: tuple[str, ...]


def _names(text: str, known: frozenset[str] = frozenset()) -> set[str]:
    """Capitalised words inside a sentence, which name a product, company or place. A word that
    starts a sentence counts only when it is a known name, so "Platforms" is never one."""
    names = set()
    for match in _NAME.finditer(text):
        before = text[: match.start()].rstrip()
        if (before and before[-1] not in _SENTENCE_END) or match.group(0) in known:
            names.add(match.group(0))
    return names


def _format_count(value: float) -> str:
    for scale, name in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if value >= scale:
            return f"{value / scale:g} {name}"
    return f"{value:,.0f}"


def _metric(words: set[str]) -> str:
    if len(words) == 1:
        word = next(iter(words))
        return word if word.endswith("s") else f"{word}s"
    return f"{' and '.join(sorted(words))} counts"


def _listed(members: list[tuple[int, float]], claims: list[Claim]) -> str:
    """Each distinct value once, in claim order, with every source that gives it."""
    seen: list[tuple[float, list[str]]] = []
    for index, value in members:
        ids = list(claims[index].source_ids)
        match = next((item for item in seen if math.isclose(item[0], value, rel_tol=1e-9)), None)
        if match is None:
            seen.append((value, ids))
        else:
            match[1].extend(sid for sid in ids if sid not in match[1])
    return ", ".join(f"{_format_count(value)} ({', '.join(ids) or 'no source'})" for value, ids in seen)


def count_conflicts(claims: list[Claim], context: list[str] | tuple[str, ...] = ()) -> list[str]:
    """One note per named product and measure for which the claims give different counts.

    Two counts conflict when their claims name the same product, they count the same thing
    (share a describing word, so downloads never conflict with farmers), their values differ and
    they come from different claims. Small counts are left out. The words of one measure, such as
    "active users", share one note. A name is a capitalised word used inside a sentence, in a
    claim or in the `context` texts (the evidence snippets), so "Plantix has 10 million downloads"
    names Plantix once a snippet says "...such as Plantix...".
    """
    known = frozenset().union(*(_names(text) for text in [*(claim.text for claim in claims), *context]))
    entries: list[tuple[int, str, str, float]] = []  # claim index, name, counted word, value
    for index, claim in enumerate(claims):
        counts = [
            amount
            for amount in read(claim.text).amounts
            if amount.kind == "count" and amount.words and (amount.scaled or amount.value >= MIN_COUNT)
        ]
        for name in sorted(_names(claim.text, known)):
            entries += [(index, name, word, amount.value) for amount in counts for word in sorted(amount.words)]

    groups: dict[tuple[str, tuple[tuple[int, float], ...]], list[str]] = {}
    for name, word in sorted({(entry[1], entry[2]) for entry in entries}):
        members = tuple(sorted({(entry[0], entry[3]) for entry in entries if entry[1:3] == (name, word)}))
        values = {round(value, 6) for _, value in members}
        if len(values) > 1 and len({index for index, _ in members}) > 1:
            groups.setdefault((name, members), []).append(word)

    return [
        f"Sources give different figures for {name} {_metric(set(words))}: {_listed(list(members), claims)}. "
        "They may differ in date or definition, so check the sources before using either."
        for (name, members), words in groups.items()
    ]
