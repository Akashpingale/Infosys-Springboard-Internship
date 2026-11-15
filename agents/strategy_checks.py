import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from agents.figures import NO_AMOUNTS, STOP_WORDS, SUPPORTED, check_claim, singular
from agents.strategy_context import (
    ASSUMPTION,
    CONSTRAINT_PREFIX,
    IDEA_PREFIX,
    INTERPRETATION,
    USER_PROVIDED,
    Digest,
    normalize_ref,
    ref_prefix,
    to_source_key,
)
from config import get_settings
from models.schemas import StrategySourceKey
from utils.errors import AppError

Item = TypeVar("Item", bound=BaseModel)

REF_FIELD = "based_on"
CROSS_REF_FIELDS = frozenset({"based_on", "refs", "mitigates", "uses_features", "addresses_risks"})
MAIN_TEXT_FIELDS = ("name", "title", "text", "tactic", "description")
FOUNDER_PREFIXES = frozenset({IDEA_PREFIX, CONSTRAINT_PREFIX})

OVERCLAIM_PHRASES = ("guaranteed", "will succeed", "no competition", "risk-free", "certain to", "can't fail")
DUPLICATE_THRESHOLD = 0.8
ELLIPSIS = "..."
SECRET_MIN_CHARS = 8

REF_REMOVED = "strategy_ref_removed"
BASIS_ADJUSTED = "strategy_basis_adjusted"
FIGURE_REMOVED = "strategy_figure_removed"
OVERCLAIM_REMOVED = "strategy_overclaim_removed"
DUPLICATE_REMOVED = "strategy_duplicate_removed"
ITEMS_CUT = "strategy_items_cut"
TEXT_SHORTENED = "strategy_text_shortened"
WARNING_CODES = (
    REF_REMOVED,
    BASIS_ADJUSTED,
    FIGURE_REMOVED,
    OVERCLAIM_REMOVED,
    DUPLICATE_REMOVED,
    ITEMS_CUT,
    TEXT_SHORTENED,
)

KEY_SHAPES = (
    ("key-shaped text (Google)", r"(?<![0-9A-Za-z])AIza[0-9A-Za-z_\-]{30,}"),
    ("key-shaped text (Gemini)", r"(?<![0-9A-Za-z])AQ\.[0-9A-Za-z_\-]{20,}"),
    ("key-shaped text (Tavily)", r"(?<![0-9A-Za-z])tvly-[0-9A-Za-z_\-]{10,}"),
    ("key-shaped text (Groq)", r"(?<![0-9A-Za-z])gsk_[0-9A-Za-z]{20,}"),
    ("key-shaped text (secret key)", r"(?<![0-9A-Za-z])sk-(?=[0-9A-Za-z_\-]*\d)[0-9A-Za-z_\-]{20,}"),
    ("bearer token", r"\b(?i:bearer)\s+(?=[0-9A-Za-z._~+/\-]*\d)[0-9A-Za-z._~+/\-]{16,}=*"),
    ("private key block", r"-----BEGIN [A-Z ]*KEY-----"),
)
CONFIGURED_KEY = "configured key value"

_KEY_PATTERNS = tuple((label, re.compile(pattern)) for label, pattern in KEY_SHAPES)
_WORD = re.compile(r"[^\W_]+")


def _phrase_pattern(phrase: str) -> str:
    words = re.split(r"[\s-]+", phrase)
    return r"\b" + r"[\s-]+".join(re.escape(word).replace("'", "['’]") for word in words) + r"\b"


_OVERCLAIM = re.compile("|".join(f"(?P<p{index}>{_phrase_pattern(phrase)})" for index, phrase in enumerate(OVERCLAIM_PHRASES)), re.IGNORECASE)


@dataclass
class Repairs:
    refs_removed: list[str] = field(default_factory=list)
    to_assumption: int = 0
    to_interpretation: int = 0
    figures_removed: int = 0
    overclaims_removed: int = 0
    overclaim_phrases: list[str] = field(default_factory=list)
    duplicates_removed: int = 0
    cut: dict[str, int] = field(default_factory=dict)
    shortened: int = 0

    def warnings(self) -> list[str]:
        built = (
            ref_removed_warning(self.refs_removed),
            basis_adjusted_warning(self.to_assumption, self.to_interpretation),
            figure_removed_warning(self.figures_removed),
            overclaim_removed_warning(self.overclaims_removed, self.overclaim_phrases),
            duplicate_removed_warning(self.duplicates_removed),
            items_cut_warning(self.cut),
            text_shortened_warning(self.shortened),
        )
        return [warning for warning in built if warning]


def _points(count: int) -> str:
    return f"{count} point" if count == 1 else f"{count} points"


def ref_removed_warning(refs: Sequence[str]) -> str | None:
    if not refs:
        return None
    links = "link" if len(refs) == 1 else "links"
    return f"removed {len(refs)} {links} to findings that are not in the digest ({', '.join(refs)})"


def basis_adjusted_warning(to_assumption: int, to_interpretation: int) -> str | None:
    parts = []
    if to_assumption:
        parts.append(f"{_points(to_assumption)} without an existing finding now marked as assumptions")
    if to_interpretation:
        parts.append(
            f"{_points(to_interpretation)} attributed to the founder without an idea or constraint fact now marked "
            "as AI interpretations"
        )
    return f"basis changed: {'; '.join(parts)}" if parts else None


def figure_removed_warning(count: int) -> str | None:
    return f"removed {_points(count)} that stated a figure no cited finding contains" if count else None


def overclaim_removed_warning(count: int, phrases: Sequence[str]) -> str | None:
    if not count:
        return None
    return f"removed {_points(count)} that promised an outcome ({', '.join(dict.fromkeys(phrases))})"


def duplicate_removed_warning(count: int) -> str | None:
    return f"removed {_points(count)} that repeated an earlier point" if count else None


def items_cut_warning(cut: Mapping[str, int]) -> str | None:
    listed = [f"{label} {count}" for label, count in cut.items() if count]
    return f"cut points beyond the list limits ({', '.join(listed)})" if listed else None


def text_shortened_warning(count: int) -> str | None:
    texts = "text" if count == 1 else "texts"
    return f"shortened {count} {texts} over the length limit at a word boundary" if count else None


def split_refs(refs: Iterable[object], digest: Digest) -> tuple[list[str], list[str]]:
    known = digest.refs
    kept: list[str] = []
    removed: list[str] = []
    for ref in refs:
        normalized = normalize_ref(ref)
        if not normalized:
            continue
        if normalized in known:
            if normalized not in kept:
                kept.append(normalized)
        else:
            removed.append(str(ref).strip())
    return kept, removed


def _basis_value(basis: object) -> str:
    return str(getattr(basis, "value", basis))


def adjusted_basis(basis: object, valid_refs: Sequence[str]) -> str:
    value = _basis_value(basis)
    if not valid_refs and value in (INTERPRETATION, USER_PROVIDED):
        return ASSUMPTION
    if value == USER_PROVIDED and not any(ref_prefix(ref) in FOUNDER_PREFIXES for ref in valid_refs):
        return INTERPRETATION
    return value


def inherited_sources(valid_refs: Iterable[str], digest: Digest) -> list[StrategySourceKey]:
    keys: list[str] = []
    for ref in valid_refs:
        fact = digest.fact(ref)
        for key in fact.sources if fact else ():
            if key not in keys:
                keys.append(key)
    return [to_source_key(key) for key in keys]


def item_texts(item: BaseModel) -> list[str]:
    texts: list[str] = []
    for name in type(item).model_fields:
        if name in CROSS_REF_FIELDS:
            continue
        value = getattr(item, name)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts += [entry for entry in value if isinstance(entry, str)]
    return texts


def main_text(item: BaseModel) -> str:
    return " ".join(str(getattr(item, name)) for name in MAIN_TEXT_FIELDS if isinstance(getattr(item, name, None), str))


def cited_texts(valid_refs: Iterable[str], digest: Digest) -> list[str]:
    return [fact.text for fact in (digest.fact(ref) for ref in valid_refs) if fact is not None]


def figure_supported(text: str | None, valid_refs: Iterable[str], digest: Digest) -> bool:
    return check_claim(text, cited_texts(valid_refs, digest)) in (NO_AMOUNTS, SUPPORTED)


def has_unsupported_figure(item: BaseModel, valid_refs: Sequence[str], digest: Digest) -> bool:
    cited = cited_texts(valid_refs, digest)
    return any(check_claim(text, cited) not in (NO_AMOUNTS, SUPPORTED) for text in item_texts(item))


def overclaims(texts: Iterable[str]) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in _OVERCLAIM.finditer(text or ""):
            phrase = OVERCLAIM_PHRASES[int(match.lastgroup[1:])]
            if phrase not in found:
                found.append(phrase)
    return found


def check_item(item: Item, digest: Digest, repairs: Repairs, *, ref_field: str = REF_FIELD) -> Item | None:
    kept, removed = split_refs(getattr(item, ref_field), digest)
    if has_unsupported_figure(item, kept, digest):
        repairs.figures_removed += 1
        return None
    phrases = overclaims(item_texts(item))
    if phrases:
        repairs.overclaims_removed += 1
        repairs.overclaim_phrases += phrases
        return None
    repairs.refs_removed += removed
    original = _basis_value(getattr(item, "basis"))
    basis = adjusted_basis(original, kept)
    if basis != original:
        if basis == ASSUMPTION:
            repairs.to_assumption += 1
        else:
            repairs.to_interpretation += 1
    return item.model_copy(update={ref_field: kept, "basis": basis})


def tokens(text: str | None) -> frozenset[str]:
    return frozenset(singular(word) for word in _WORD.findall((text or "").lower()) if word not in STOP_WORDS)


def token_overlap(first: str | None, second: str | None) -> float:
    a, b = tokens(first), tokens(second)
    if not a or not b:
        return float(a == b)
    return len(a & b) / max(len(a), len(b))


def remove_duplicates(
    items: Sequence[Item], repairs: Repairs, *, text_of: Callable[[BaseModel], str] = main_text
) -> list[Item]:
    kept: list[Item] = []
    for item in items:
        if any(token_overlap(text_of(item), text_of(earlier)) >= DUPLICATE_THRESHOLD for earlier in kept):
            repairs.duplicates_removed += 1
            continue
        kept.append(item)
    return kept


def cut_to_limit(items: Sequence[Item], maximum: int, label: str, repairs: Repairs) -> list[Item]:
    extra = len(items) - maximum
    if extra > 0:
        repairs.cut[label] = repairs.cut.get(label, 0) + extra
        return list(items[:maximum])
    return list(items)


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= len(ELLIPSIS):
        return text[:limit]
    budget = limit - len(ELLIPSIS)
    space = text.rfind(" ", 0, budget + 1)
    head = text[:space] if space > 0 else text[:budget]
    return head.rstrip(" ,;:.-") + ELLIPSIS


def shorten_fields(item: Item, lengths: Mapping[str, int], repairs: Repairs) -> Item:
    updates: dict[str, object] = {}
    for name, limit in lengths.items():
        value = getattr(item, name, None)
        if isinstance(value, str) and len(value) > limit:
            updates[name] = shorten(value, limit)
            repairs.shortened += 1
        elif isinstance(value, list) and any(isinstance(entry, str) and len(entry) > limit for entry in value):
            repairs.shortened += sum(isinstance(entry, str) and len(entry) > limit for entry in value)
            updates[name] = [shorten(entry, limit) if isinstance(entry, str) else entry for entry in value]
    return item.model_copy(update=updates) if updates else item


def check_items(
    items: Sequence[Item],
    digest: Digest,
    repairs: Repairs,
    *,
    label: str,
    maximum: int | None = None,
    lengths: Mapping[str, int] | None = None,
    ref_field: str = REF_FIELD,
    text_of: Callable[[BaseModel], str] = main_text,
) -> list[Item]:
    checked = [found for found in (check_item(item, digest, repairs, ref_field=ref_field) for item in items) if found is not None]
    checked = remove_duplicates(checked, repairs, text_of=text_of)
    if maximum is not None:
        checked = cut_to_limit(checked, maximum, label, repairs)
    return [shorten_fields(item, lengths, repairs) for item in checked] if lengths else checked


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, BaseModel):
        yield from _strings(value.model_dump(mode="json"))
    elif isinstance(value, Mapping):
        for key, entry in value.items():
            yield from _strings(key)
            yield from _strings(entry)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for entry in value:
            yield from _strings(entry)
    elif isinstance(value, str):
        yield value


def configured_secrets() -> tuple[str, ...]:
    settings = get_settings()
    values = (settings.llm_api_key, settings.tavily_api_key, settings.groq_api_key)
    return tuple(value for value in values if value and len(value) >= SECRET_MIN_CHARS)


def secret_findings(value: object) -> list[str]:
    secrets = configured_secrets()
    found: list[str] = []
    for text in _strings(value):
        labels = [CONFIGURED_KEY] if any(secret in text for secret in secrets) else []
        labels += [label for label, pattern in _KEY_PATTERNS if pattern.search(text)]
        found += [label for label in labels if label not in found]
    return found


def ensure_no_secrets(value: object) -> None:
    if secret_findings(value):
        raise AppError()
