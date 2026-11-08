"""Evidence-integrity checks and safe repairs shared by the analysis agents.

Pure functions with no I/O and no LLM calls, so agents, tests and the live runner can all
use them. Checks return a list of violations (an empty list means clean). Repairs return a
fixed copy plus one warning per change; they never invent content.

The checks read fields by the names fixed in KIRO_PROMPT_M2.md Sections 5.2, 7.1 and 8.1
(`source_ids`, `basis`, `status`, `value`, `url`, `website`, `strengths`, `weaknesses`,
`caveats`, `market_gaps`), plus the Task 1 market-size `scope`. URLs and domains use the same normalisation as evidence building;
a website must be an http or https URL on an evidence domain. The search summary S0 never
backs a URL, a website or a listed source.
"""

import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from agents.evidence import domain_of, is_summary_id, normalize_url, sourced_items
from models.schemas import MARKET_SCOPES, Basis, EvidenceItem, SourceRef

MARKET_CAVEAT = "Market figures are evidence-dependent and need verification."
COMPETITOR_CAVEAT = (
    "Absence from search results does not prove a competitor or a gap does not exist."
)

SOURCED = "sourced"
ESTIMATE = "estimate_needs_verification"
UNAVAILABLE = "unavailable"
GAP_CONFIDENCES = ("low", "medium")
URL_FIELDS = frozenset({"url"})
WEBSITE_FIELDS = frozenset({"website"})
TEXT_FIELDS = frozenset({"name", "text", "trend", "description"})
SUPPORT_REQUIRED_LISTS = frozenset({"strengths", "weaknesses"})
FIGURE_FIELDS = frozenset({"value", "status", "source_ids"})
HTTP_SCHEMES = frozenset({"http", "https"})
MARKET_SIZE_FIELDS = ("tam", "sam", "som")
IDEA_MARKET = MARKET_SCOPES[0]
EVIDENCE_FOUND = "evidence_found"

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?"

__all__ = [
    "COMPETITOR_CAVEAT",
    "MARKET_CAVEAT",
    "check_competitor_integrity",
    "check_market_integrity",
    "domain_in_evidence",
    "domain_of",
    "evidence_ids",
    "find_violations",
    "normalize_url",
    "remove_foreign_urls",
    "repair_tree",
    "supporting_source_ids",
    "url_in_evidence",
    "valid_source_ids",
    "website_in_evidence",
]


# --- URL and domain matching ------------------------------------------------


def _evidence_urls(evidence: list[EvidenceItem]) -> set[str]:
    """URLs that can back a claim. The search summary S0 never counts, even if given a URL."""
    return {normalize_url(item.url) for item in sourced_items(evidence)} - {""}


def _evidence_domains(evidence: list[EvidenceItem]) -> set[str]:
    return {domain_of(item.url) for item in sourced_items(evidence)} - {""}


def url_in_evidence(url: str, evidence: list[EvidenceItem]) -> bool:
    """A malformed URL normalises to an empty string and never matches."""
    normalized = normalize_url(url)
    return bool(normalized) and normalized in _evidence_urls(evidence)


def domain_in_evidence(url_or_domain: str, evidence: list[EvidenceItem]) -> bool:
    """True when the domain equals an evidence domain or is a subdomain of one.

    A look-alike such as `leafdoc.example.evil.net` does not match `leafdoc.example`, and a
    malformed URL never matches.
    """
    candidate = domain_of(url_or_domain)
    if not candidate:
        return False
    return any(candidate == known or candidate.endswith(f".{known}") for known in _evidence_domains(evidence))


def _website_problem(website: str, evidence: list[EvidenceItem]) -> str | None:
    """Why a website value is not allowed, or None when it is.

    Section 8.1: a website is null unless it matches an evidence domain. Only a plain http
    or https URL with a host and no spaces or control characters is accepted, so
    `javascript:`, `data:` and other schemes are rejected even on a matching host.
    """
    text = (website or "").strip()
    if not text:
        return "it is empty"
    invalid = "it is not a valid http or https URL"
    if any(char.isspace() or not char.isprintable() for char in text):
        return invalid
    try:
        parts = urlsplit(text)
    except ValueError:
        return invalid
    if parts.scheme.lower() not in HTTP_SCHEMES or not parts.hostname:
        return invalid
    if not domain_in_evidence(text, evidence):
        return "it matches no evidence domain"
    return None


def website_in_evidence(website: str, evidence: list[EvidenceItem]) -> bool:
    """True only for an http or https URL whose domain is an evidence domain."""
    return _website_problem(website, evidence) is None


# --- source ids ---------------------------------------------------------------


def _norm_id(source_id: str) -> str:
    return str(source_id).strip().upper()


def evidence_ids(evidence: list[EvidenceItem]) -> set[str]:
    return {_norm_id(item.id) for item in evidence}


def valid_source_ids(source_ids: list[str], evidence: list[EvidenceItem]) -> list[str]:
    """Known ids only, in their original order, normalised (s1 becomes S1) and de-duplicated."""
    known = evidence_ids(evidence)
    kept: list[str] = []
    for source_id in source_ids:
        normalized = _norm_id(source_id)
        if normalized in known and normalized not in kept:
            kept.append(normalized)
    return kept


def supporting_source_ids(source_ids: list[str], evidence: list[EvidenceItem]) -> list[str]:
    """Known ids that can back a sourced claim: the search summary S0 never can."""
    return [sid for sid in valid_source_ids(source_ids, evidence) if not is_summary_id(sid)]


def _is_sourced(value: object) -> bool:
    return value == SOURCED  # Basis is a str enum, so Basis.sourced compares equal too


def _is_figure(model: BaseModel) -> bool:
    """A QuantEstimate, or any model shaped like one (Section 8.1 `pricing_model`)."""
    return FIGURE_FIELDS <= set(type(model).model_fields)


def _has_value(model: BaseModel) -> bool:
    value = getattr(model, "value", None)
    return value is not None and str(value).strip() != ""


def _ids(model: BaseModel) -> list[str]:
    return list(getattr(model, "source_ids", None) or [])


# --- repairs ------------------------------------------------------------------


def _repair_figure(
    model: BaseModel, evidence: list[EvidenceItem], label: str
) -> tuple[BaseModel, list[str]]:
    """Rules 4 and 7.2: a figure exists only when the evidence backs it.

    sourced:   needs a real source; resting only on S0 makes it an estimate; citing
               nothing valid makes it unavailable.
    estimate:  a figure must cite some evidence (S0 counts); otherwise unavailable.
    unavailable: never keeps a figure.
    """
    status = getattr(model, "status", None)
    ids = _ids(model)
    unavailable = {"status": UNAVAILABLE, "value": None}

    if _is_sourced(status) and not supporting_source_ids(ids, evidence):
        if _has_value(model) and valid_source_ids(ids, evidence):
            warning = f"{label}: figure rests only on the search summary, so it needs verification"
            return model.model_copy(update={"status": ESTIMATE}), [warning]
        warning = f"{label}: figure marked sourced cited no valid source, so it is now unavailable"
        return model.model_copy(update=unavailable), [warning]

    if status == ESTIMATE and _has_value(model) and not valid_source_ids(ids, evidence):
        warning = f"{label}: estimated figure cited no evidence, so it is now unavailable"
        return model.model_copy(update=unavailable), [warning]

    if status == UNAVAILABLE and getattr(model, "value", None) is not None:
        warning = f"{label}: removed a figure from an item marked unavailable"
        return model.model_copy(update={"value": None}), [warning]

    return model, []


def _repair_support(
    model: BaseModel, evidence: list[EvidenceItem], label: str
) -> tuple[BaseModel, list[str]]:
    """Downgrade a sourced claim, or repair a figure, whose sources are not valid evidence."""
    fields = type(model).model_fields
    if "source_ids" not in fields:
        return model, []
    if _is_figure(model):
        return _repair_figure(model, evidence, label)

    basis = getattr(model, "basis", None)
    if isinstance(basis, Basis) and basis is Basis.sourced and not supporting_source_ids(_ids(model), evidence):
        warning = f"{label}: a sourced claim had no valid source, so it is now an AI interpretation"
        return model.model_copy(update={"basis": Basis.ai_interpretation}), [warning]
    return model, []


def _short(text: object) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= 60 else text[:57] + "..."


def _repair_list(
    name: str, items: list, evidence: list[EvidenceItem], where: str
) -> tuple[list, list[str], bool]:
    """Repair each item. In strengths and weaknesses (Section 8.3), an item with no valid
    source is removed rather than relabelled."""
    fixed_items, warnings, changed = [], [], False
    for index, item in enumerate(items):
        here = f"{where}[{index}]"
        if not isinstance(item, BaseModel):
            fixed_items.append(item)
            continue
        if name in SUPPORT_REQUIRED_LISTS and not supporting_source_ids(_ids(item), evidence):
            warnings.append(f"{here}: removed {name[:-1]} {_short(getattr(item, 'text', ''))!r}; it had no valid source")
            changed = True
            continue
        fixed, found = repair_tree(item, evidence, here)
        warnings += found
        changed = changed or fixed is not item
        fixed_items.append(fixed)
    return fixed_items, warnings, changed


def repair_tree(
    model: BaseModel, evidence: list[EvidenceItem], where: str = ""
) -> tuple[BaseModel, list[str]]:
    """Repair, not reject: drop unknown source ids, set a website to None unless it is an
    http or https URL on an evidence domain (an empty website too), remove unsupported
    strengths and weaknesses, downgrade sourced claims that lost their support, and remove
    unsupported figures.

    Returns a new model (the input is never mutated) and one warning per repair.
    """
    label = where or type(model).__name__
    warnings: list[str] = []
    updates: dict[str, object] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        here = f"{where}.{name}" if where else name
        if name == "source_ids" and isinstance(value, list):
            kept = valid_source_ids(value, evidence)
            dropped = [str(sid) for sid in value if _norm_id(sid) not in kept]
            if dropped:
                warnings.append(f"{here}: removed unknown source id(s) {', '.join(dropped)}")
            if kept != value:
                updates[name] = kept
        elif name in WEBSITE_FIELDS and isinstance(value, str):
            reason = _website_problem(value, evidence)
            if reason:
                updates[name] = None
                if value.strip():
                    warnings.append(f"{here}: removed website {_short(value)!r}; {reason}")
                else:
                    warnings.append(f"{here}: replaced an empty website with null")
        elif isinstance(value, BaseModel):
            fixed, found = repair_tree(value, evidence, here)
            warnings += found
            if fixed is not value:
                updates[name] = fixed
        elif isinstance(value, list):
            fixed_items, found, changed = _repair_list(name, value, evidence, here)
            warnings += found
            if changed:
                updates[name] = fixed_items

    if updates:
        model = model.model_copy(update=updates)
    model, found = _repair_support(model, evidence, label)
    return model, warnings + found


LINK_REMOVED = "[link removed]"


def _scrub_links(text: str, evidence: list[EvidenceItem]) -> tuple[str, int]:
    """Replace each http(s) URL that is not an evidence URL with a marker; count them."""
    removed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        found = match.group(0)
        url = found.rstrip(_TRAILING_PUNCTUATION)
        if url_in_evidence(url, evidence):
            return found
        removed += 1
        return LINK_REMOVED + found[len(url):]

    return _URL_IN_TEXT.sub(replace, text), removed


def remove_foreign_urls(
    model: BaseModel, evidence: list[EvidenceItem], where: str = ""
) -> tuple[BaseModel, list[str]]:
    """Section 7.3, "every URL in the output exists in the search evidence": replace links in
    free text that are not evidence URLs with a marker, one warning per changed field.

    Covers exactly the text that find_violations checks, so a cleaned result has no
    URL-in-text violation. Listed sources are checked as sources and are left alone.
    """
    if isinstance(model, SourceRef):
        return model, []
    warnings: list[str] = []
    updates: dict[str, object] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        here = f"{where}.{name}" if where else name
        if name == "source_ids" or name in WEBSITE_FIELDS or name in URL_FIELDS:
            continue
        if isinstance(value, str):
            cleaned, removed = _scrub_links(value, evidence)
            if removed:
                updates[name] = cleaned
                warnings.append(f"{here}: removed {removed} link(s) that are not in the search evidence")
        elif isinstance(value, BaseModel):
            fixed, found = remove_foreign_urls(value, evidence, here)
            warnings += found
            if fixed is not value:
                updates[name] = fixed
        elif isinstance(value, list):
            items, changed = [], False
            for index, item in enumerate(value):
                spot = f"{here}[{index}]"
                if isinstance(item, BaseModel):
                    fixed, found = remove_foreign_urls(item, evidence, spot)
                    warnings += found
                    changed = changed or fixed is not item
                    items.append(fixed)
                elif isinstance(item, str):
                    cleaned, removed = _scrub_links(item, evidence)
                    if removed:
                        warnings.append(f"{spot}: removed {removed} link(s) that are not in the search evidence")
                        changed = True
                    items.append(cleaned)
                else:
                    items.append(item)
            if changed:
                updates[name] = items
    return (model.model_copy(update=updates) if updates else model), warnings


# --- checks -------------------------------------------------------------------


def _schema_violations(model: BaseModel) -> list[str]:
    """Re-validate, which catches invalid enum values left by a careless repair."""
    try:
        type(model).model_validate(model.model_dump(warnings=False))
    except ValidationError as exc:
        return [
            f"{'.'.join(str(part) for part in err['loc']) or 'result'}: {err['msg']}"
            for err in exc.errors(include_input=False)
        ]
    return []


def _text_violations(text: str, here: str, check_empty: bool, evidence: list[EvidenceItem]) -> list[str]:
    problems = [f"{here}: is empty"] if check_empty and not text.strip() else []
    for url in _URL_IN_TEXT.findall(text):
        url = url.rstrip(_TRAILING_PUNCTUATION)
        if not url_in_evidence(url, evidence):
            problems.append(f"{here}: mentions URL {_short(url)!r} that is not in the evidence")
    return problems


def _source_ref_violations(ref: SourceRef, evidence: list[EvidenceItem], label: str) -> list[str]:
    """A listed source must be a real evidence item, never S0, with that item's own URL."""
    source_id = _norm_id(ref.id)
    if is_summary_id(source_id):
        return [f"{label}: the search summary {source_id} cannot be listed as a source"]
    item = next((e for e in evidence if _norm_id(e.id) == source_id), None)
    if item is None:
        return [f"{label}: unknown source id {ref.id!r}"]
    ref_url = normalize_url(ref.url)
    if not ref_url or ref_url != normalize_url(item.url):
        return [f"{label}: URL {_short(ref.url)!r} does not match evidence item {source_id}"]
    return []


def _figure_violations(model: BaseModel, evidence: list[EvidenceItem], label: str) -> list[str]:
    """At most one finding per figure, mirroring the rules _repair_figure applies."""
    ids = _ids(model)
    status = getattr(model, "status", None)
    if status == UNAVAILABLE:
        if getattr(model, "value", None) is not None:
            return [f"{label}: an unavailable figure must have no value"]
        return []
    if _is_sourced(status):
        if not supporting_source_ids(ids, evidence):
            return [f"{label}: figure marked sourced has no valid source"]
        return []
    if _has_value(model) and not valid_source_ids(ids, evidence):
        return [f"{label}: figure has a value but cites no valid evidence"]
    return []


def find_violations(
    model: BaseModel, evidence: list[EvidenceItem], where: str = ""
) -> list[str]:
    """Walk a result model and report every integrity problem against the evidence."""
    label = where or type(model).__name__
    if isinstance(model, SourceRef):
        return _source_ref_violations(model, evidence, label)

    known = evidence_ids(evidence)
    problems: list[str] = []
    for name in type(model).model_fields:
        value = getattr(model, name)
        here = f"{where}.{name}" if where else name
        if name == "source_ids" and isinstance(value, list):
            problems += [
                f"{here}: unknown source id {sid!r}" for sid in value if _norm_id(sid) not in known
            ]
        elif name in WEBSITE_FIELDS and isinstance(value, str):
            reason = _website_problem(value, evidence)
            if reason:
                problems.append(f"{here}: website {_short(value)!r} is not allowed: {reason}")
        elif name in URL_FIELDS and isinstance(value, str) and value.strip():
            if not url_in_evidence(value, evidence):
                problems.append(f"{here}: URL {_short(value)!r} is not in the evidence")
        elif isinstance(value, str):
            problems += _text_violations(value, here, name in TEXT_FIELDS, evidence)
        elif isinstance(value, BaseModel):
            problems += find_violations(value, evidence, here)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, BaseModel):
                    problems += find_violations(item, evidence, f"{here}[{index}]")
                elif isinstance(item, str):
                    problems += _text_violations(item, f"{here}[{index}]", True, evidence)

    fields = type(model).model_fields
    if "source_ids" in fields:
        if _is_figure(model):
            problems += _figure_violations(model, evidence, label)
        elif _is_sourced(getattr(model, "basis", None)) and not supporting_source_ids(_ids(model), evidence):
            problems.append(f"{label}: sourced claim has no valid source")
    return problems


def _has_caveat(model: BaseModel, caveat: str) -> bool:
    return caveat in (getattr(model, "caveats", None) or [])


def _market_scope_violations(result: BaseModel) -> list[str]:
    """Task 1: a TAM, SAM or SOM that has a figure must measure this idea's own market. Only
    figure models with a `scope` field are checked."""
    size = getattr(result, "market_size", None)
    problems = []
    for name in MARKET_SIZE_FIELDS:
        figure = getattr(size, name, None)
        if not isinstance(figure, BaseModel) or "scope" not in type(figure).model_fields:
            continue
        if _has_value(figure) and figure.scope != IDEA_MARKET:
            problems.append(f"market_size.{name}: a figure for a broader or unknown market cannot be the {name.upper()}")
    return problems


def check_market_integrity(result: BaseModel, evidence: list[EvidenceItem]) -> list[str]:
    """Violations in a Market Opportunity result (Sections 5.4 and 7)."""
    problems = _schema_violations(result) + find_violations(result, evidence)
    problems += _market_scope_violations(result)
    if not _has_caveat(result, MARKET_CAVEAT):
        problems.append(f"caveats: the required caveat {MARKET_CAVEAT!r} is missing")
    return problems


def _unsupported_strengths_and_weaknesses(result: BaseModel, evidence: list[EvidenceItem]) -> list[str]:
    """Section 8.1: every strength and weakness needs a valid source, whatever its basis."""
    problems = []
    for c_index, competitor in enumerate(getattr(result, "competitors", None) or []):
        for name in sorted(SUPPORT_REQUIRED_LISTS):
            for i_index, item in enumerate(getattr(competitor, name, None) or []):
                if supporting_source_ids(_ids(item), evidence):
                    continue
                if _is_sourced(getattr(item, "basis", None)):
                    continue  # already reported by find_violations as an unsupported sourced claim
                problems.append(f"competitors[{c_index}].{name}[{i_index}]: has no valid source")
    return problems


def _comparison_violations(result: BaseModel, evidence: list[EvidenceItem]) -> list[str]:
    """Section 8.1 comparison matrix: a cell marked evidence_found needs a real source, and
    `feature_coverage` must equal the count of evidence_found cells per feature."""
    comparison = getattr(result, "comparison", None)
    if comparison is None:
        return []
    rows = getattr(comparison, "rows", None) or []
    problems = []
    for r_index, row in enumerate(rows):
        for c_index, cell in enumerate(getattr(row, "cells", None) or []):
            if getattr(cell, "status", None) == EVIDENCE_FOUND and not supporting_source_ids(_ids(cell), evidence):
                problems.append(f"comparison.rows[{r_index}].cells[{c_index}]: evidence_found needs a valid source")
    coverage = getattr(comparison, "feature_coverage", None)
    if coverage is not None:
        features = list(getattr(comparison, "features", None) or [])
        counted = [
            (feature, sum(cell.feature == feature and cell.status == EVIDENCE_FOUND for row in rows for cell in row.cells))
            for feature in features
        ]
        if [(item.feature, item.competitors_with_evidence) for item in coverage] != counted:
            problems.append("comparison.feature_coverage: does not match the comparison rows")
    return problems


def check_competitor_integrity(result: BaseModel, evidence: list[EvidenceItem]) -> list[str]:
    """Violations in a Competitor Analysis result (Sections 5.4 and 8)."""
    problems = _schema_violations(result) + find_violations(result, evidence)
    problems += _unsupported_strengths_and_weaknesses(result, evidence)
    problems += _comparison_violations(result, evidence)
    if not _has_caveat(result, COMPETITOR_CAVEAT):
        problems.append(f"caveats: the required caveat {COMPETITOR_CAVEAT!r} is missing")
    for index, gap in enumerate(getattr(result, "market_gaps", None) or []):
        if not str(getattr(gap, "caveat", "") or "").strip():
            problems.append(f"market_gaps[{index}].caveat: every gap must carry a caveat")
        confidence = getattr(gap, "confidence", None)
        if confidence not in GAP_CONFIDENCES:
            problems.append(
                f"market_gaps[{index}].confidence: must be low or medium, not {confidence!r}"
            )
    return problems
