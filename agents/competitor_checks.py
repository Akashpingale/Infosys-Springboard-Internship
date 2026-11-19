"""Deterministic checks for the Competitor Analysis Agent (KIRO_PROMPT_M2.md Section 8.3).

Pure functions with no I/O and no LLM calls. A competitor must be named in the evidence it
cites, or by the founder in the submission; nothing is invented, and every change comes with a
warning. The generic repairs (unknown source ids, foreign websites, unsupported strengths and
weaknesses, figures) run first in agents/integrity.py; these checks build on them.
"""

import re

from agents.evidence import domain_of
from agents.figures import STOP_WORDS, SUPPORTED, check_figure, read
from agents.integrity import COMPETITOR_CAVEAT, supporting_source_ids
from models.schemas import (
    CANDIDATES_MAX,
    COMPARISON_FEATURES_MAX,
    Comparison,
    ComparisonCell,
    ComparisonDraft,
    ComparisonRow,
    Competitor,
    CompetitorCandidate,
    CompetitorDraft,
    EvidenceItem,
    FeatureCoverage,
    IdeaSubmission,
    LabeledItem,
    MarketGap,
    MarketGapDraft,
)

# Section 8.3: "strip suffixes such as Inc, Ltd, Pvt, app" before comparing names, which that
# section asks for when de-duplicating. A corporate suffix is never part of a company's identity,
# so it is stripped whenever a name is compared. A product word such as "app" is stripped only
# for the de-duplication key: dropping it can leave an ordinary word, and "Crop App" reduced to
# "crop" would be "named" by any snippet that mentions a crop.
CORPORATE_SUFFIXES = frozenset(
    "inc incorporated ltd limited pvt private llc llp plc corp corporation co company gmbh".split()
)
PRODUCT_SUFFIXES = frozenset("app apps".split())
NAME_SUFFIXES = CORPORATE_SUFFIXES | PRODUCT_SUFFIXES
# A name needs this many characters to identify a company, so "AI" never matches on its own.
NAME_MIN_CHARS = 3
DOMAIN_NAME_MIN_CHARS = 3
# A name must be at least this long to stand without its product word. It is a length rule
# rather than a dictionary, so a short ordinary word such as "crop" keeps its "App".
DISTINCT_NAME_CHARS = 5
# Words a pricing description can use without them having to appear in a source.
PRICING_WORDS = frozenset("model plan plans pricing price prices based tier tiers option options".split())
CELL_RANK = {"evidence_found": 2, "no_evidence_found": 1, "unclear": 0}
PRICE_RANK = {"sourced": 2, "estimate_needs_verification": 1, "unavailable": 0}

DROPPED_CANDIDATE = "Phase A: dropped candidate"
NOT_NAMED = "it is not named in its cited sources"
NO_SOURCE = "it has no valid source"
NOT_FOUNDER_NAMED = "the founder did not name it in the submission"
WEBSITE_NOT_CITED = "no source the competitor cites is on that domain"
WEBSITE_NOT_OWN = "the domain is not named after the competitor"
PRICE_NOT_FOUND = "the pricing does not appear in its cited sources, so it needs verification"
FEATURE_WORD_MIN_CHARS = 3
FEATURE_TABLE_CORRECTED = (
    "the listed feature {feature!r} of {name!r} was marked {status} in the comparison table, but a source it cites "
    "names the feature, so the table was corrected"
)
FEATURE_REMOVED = (
    "the listed feature {feature!r} of {name!r} was marked {status} in the comparison table and no source it cites "
    "names the feature, so the feature was removed"
)

_TOKEN = re.compile(r"[^\W_]+")


# --- names -------------------------------------------------------------------------------


def _tokens(text: str | None) -> list[str]:
    return _TOKEN.findall((text or "").casefold())


def _without_suffixes(words: list[str], suffixes: frozenset[str]) -> list[str]:
    core = list(words)
    while core and core[-1] in suffixes:
        core.pop()
    return core or words


def name_tokens(name: str) -> list[str]:
    """The words of a name for matching it in text, without trailing corporate suffixes
    ("LeafDoc Pvt Ltd" is leafdoc).

    A product word such as "app" is dropped only when what remains is long enough to name a
    company on its own: "Plantix App" is plantix, while "Crop App" keeps both words, because
    "crop" alone would be "named" by any text about crops.
    """
    core = _without_suffixes(_tokens(name), CORPORATE_SUFFIXES)
    shorter = _without_suffixes(core, PRODUCT_SUFFIXES)
    return shorter if len("".join(shorter)) >= DISTINCT_NAME_CHARS else core


def name_key(name: str) -> str:
    """Section 8.3 normalised name, used to find duplicates: lower case, no company or product
    suffixes and no spaces, so "Leaf Doc Pvt Ltd", "LeafDoc" and "LeafDoc App" are one
    competitor."""
    return "".join(_without_suffixes(name_tokens(name), PRODUCT_SUFFIXES))


def mentions_name(text: str | None, name: str) -> bool:
    """True when the text names the competitor as whole words, with any spacing:
    "Map My Crop" matches "MapMyCrop", but "Crop" does not match "Cropin"."""
    joined = "".join(name_tokens(name))
    if len(joined) < NAME_MIN_CHARS:
        return False
    tokens = _tokens(text)
    widest = min(len(name_tokens(name)) + 2, 8)
    for size in range(1, widest + 1):
        for start in range(len(tokens) - size + 1):
            if "".join(tokens[start : start + size]) == joined:
                return True
    return False


def founder_text(submission: IdeaSubmission | None) -> str:
    """The submission's free-text fields, where a founder can name competitors. The UI asks for
    them under "Anything else we should know?" (relevant_details)."""
    if submission is None:
        return ""
    return " ".join([submission.idea_description, submission.relevant_details or ""])


def cited_items(source_ids: list[str], evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    """The real sources an item cites. The search summary S0 never counts."""
    by_id = {item.id.upper(): item for item in evidence}
    return [by_id[sid] for sid in supporting_source_ids(source_ids, evidence) if sid in by_id]


def _domain_label(url: str) -> str:
    """The first label of the host, where a company's own name sits: "www.leafdoc.example/x"
    gives leafdoc."""
    return re.sub(r"[^a-z0-9]", "", domain_of(url).split(".")[0])


def owns_domain(name: str, url: str) -> bool:
    """True when the URL's own domain is named after the competitor, as its own site is. The
    label must equal the name, so cropinsight.com is not the site of a "Crop App"."""
    key = name_key(name)
    return len(key) >= DOMAIN_NAME_MIN_CHARS and _domain_label(url) == key


def named_in_sources(name: str, source_ids: list[str], evidence: list[EvidenceItem]) -> bool:
    """True when a cited source names the competitor in its title or snippet, or is a page on
    the competitor's own domain: a result from leafdoc.example is evidence of LeafDoc even when
    its 300-character snippet does not repeat the name."""
    return any(
        mentions_name(f"{item.title} {item.snippet}", name) or owns_domain(name, item.url)
        for item in cited_items(source_ids, evidence)
    )


def _grounding_problem(name: str, basis: str, source_ids: list[str], evidence: list[EvidenceItem], founder: str) -> str | None:
    if basis == "user_provided":
        return None if mentions_name(founder, name) else NOT_FOUNDER_NAMED
    if not supporting_source_ids(source_ids, evidence):
        return NO_SOURCE
    return None if named_in_sources(name, source_ids, evidence) else NOT_NAMED


# --- Phase A candidates ---------------------------------------------------------------------


def check_candidates(
    candidates: list[CompetitorCandidate], evidence: list[EvidenceItem], founder: str
) -> tuple[list[CompetitorCandidate], list[str]]:
    """Keep up to CANDIDATES_MAX candidates that are named in their cited evidence, or by the
    founder; the same name twice becomes one candidate with both sets of sources."""
    kept: list[CompetitorCandidate] = []
    warnings: list[str] = []
    for candidate in candidates:
        problem = _grounding_problem(candidate.name, candidate.basis, candidate.source_ids, evidence, founder)
        if problem:
            warnings.append(f"{DROPPED_CANDIDATE} {candidate.name!r}: {problem}")
            continue
        twin = next((other for other in kept if name_key(other.name) == name_key(candidate.name)), None)
        if twin is not None:
            index = kept.index(twin)
            kept[index] = twin.model_copy(update={"source_ids": _union(twin.source_ids, candidate.source_ids)})
            continue
        if len(kept) == CANDIDATES_MAX:
            warnings.append(f"{DROPPED_CANDIDATE} {candidate.name!r}: only {CANDIDATES_MAX} candidates are kept")
            continue
        kept.append(candidate)
    return kept, warnings


# --- competitors ------------------------------------------------------------------------------


def _text(value: str | None) -> str:
    return (value or "").strip()


def _union(first: list[str], second: list[str]) -> list[str]:
    merged = list(first)
    for value in second:
        if value not in merged:
            merged.append(value)
    return merged


def _union_text(first: list[str], second: list[str]) -> list[str]:
    seen = {" ".join(value.split()).casefold() for value in first}
    merged = list(first)
    for value in second:
        key = " ".join(value.split()).casefold()
        if key not in seen:
            seen.add(key)
            merged.append(value)
    return merged


def _union_items(first: list[LabeledItem], second: list[LabeledItem]) -> list[LabeledItem]:
    seen = {" ".join(item.text.split()).casefold() for item in first}
    return [*first, *(item for item in second if " ".join(item.text.split()).casefold() not in seen)]


def _irrelevant(competitor: CompetitorDraft) -> bool:
    """Section 8.3: a competitor without a type or a relevance note is an irrelevant result."""
    return competitor.type is None or not _text(competitor.relevance_note)


def _website_problem(competitor: CompetitorDraft, evidence: list[EvidenceItem]) -> str | None:
    """A website is the competitor's own only when a source it cites is on that domain and the
    domain carries its name. A directory such as cbinsights.com is an evidence domain too, so
    the generic evidence-domain rule alone is not enough."""
    host = domain_of(competitor.website or "")
    hosts = {domain_of(item.url) for item in cited_items(competitor.source_ids, evidence)} - {""}
    if not any(host == known or host.endswith(f".{known}") or known.endswith(f".{host}") for known in hosts):
        return WEBSITE_NOT_CITED
    joined = name_key(competitor.name)
    flat = re.sub(r"[^a-z0-9]", "", host)
    if len(joined) < DOMAIN_NAME_MIN_CHARS or joined not in flat:
        return WEBSITE_NOT_OWN
    return None


def pricing_supported(value: str | None, cited_snippets: list[str]) -> bool:
    """A sourced price stays sourced only if the cited snippets state it: an amount with the
    same value and unit (agents/figures.py), or, for a price written in words such as "Free" or
    "Freemium", every distinctive word."""
    reading = read(value)
    if reading.amounts or reading.unclear:
        return check_figure(value, cited_snippets) == SUPPORTED
    words = {word for word in _tokens(value) if len(word) >= 3 and word not in STOP_WORDS | PRICING_WORDS}
    seen = {word for snippet in cited_snippets for word in _tokens(snippet)}
    return bool(words) and words <= seen


def _check_pricing(competitor: CompetitorDraft, evidence: list[EvidenceItem], label: str) -> tuple[CompetitorDraft, list[str]]:
    price = competitor.pricing_model
    if price.status != "sourced" or not _text(price.value):
        return competitor, []
    snippets = [item.snippet for item in cited_items(price.source_ids, evidence)]
    if pricing_supported(price.value, snippets):
        return competitor, []
    fixed = price.model_copy(update={"status": "estimate_needs_verification"})
    return competitor.model_copy(update={"pricing_model": fixed}), [f"{label}.pricing_model: {PRICE_NOT_FOUND}"]


def _merge(first: CompetitorDraft, second: CompetitorDraft) -> CompetitorDraft:
    """Section 8.3: duplicates merge into the first entry; lists and sources are unioned, and a
    field the first entry left empty is taken from the second."""
    def pick(name: str) -> str | None:
        return getattr(first, name) if _text(getattr(first, name)) else getattr(second, name)

    price = first.pricing_model
    if PRICE_RANK[second.pricing_model.status] > PRICE_RANK[price.status]:
        price = second.pricing_model
    fields = ("relevance_note", "offering", "target_segment", "value_proposition", "positioning", "differentiation_vs_startup")
    return first.model_copy(
        update={
            **{name: pick(name) for name in fields},
            "website": first.website or second.website,
            "source_ids": _union(first.source_ids, second.source_ids),
            "key_features": _union_text(first.key_features, second.key_features),
            "pricing_model": price,
            "strengths": _union_items(first.strengths, second.strengths),
            "weaknesses": _union_items(first.weaknesses, second.weaknesses),
            "basis": "sourced" if "sourced" in (first.basis, second.basis) else "user_provided",
        }
    )


def _same_competitor(first: CompetitorDraft, second: CompetitorDraft) -> bool:
    if name_key(first.name) == name_key(second.name):
        return True
    hosts = domain_of(first.website or ""), domain_of(second.website or "")
    return bool(hosts[0]) and hosts[0] == hosts[1]


def completeness(competitor: CompetitorDraft) -> str:
    """Section 8.1 `info_completeness`, counted in code from seven facts: offering, target
    segment, key features, value proposition, known pricing, positioning, and any strength or
    weakness. 6 or 7 known is complete, 3 to 5 partial, fewer minimal."""
    facts = [
        _text(competitor.offering),
        _text(competitor.target_segment),
        competitor.key_features,
        _text(competitor.value_proposition),
        competitor.pricing_model.status != "unavailable",
        _text(competitor.positioning),
        competitor.strengths or competitor.weaknesses,
    ]
    known = sum(bool(fact) for fact in facts)
    return "complete" if known >= 6 else "partial" if known >= 3 else "minimal"


def check_competitors(
    drafts: list[CompetitorDraft], evidence: list[EvidenceItem], founder: str
) -> tuple[list[Competitor], dict[str, str], list[str]]:
    """Section 8.3 competitor guards, in order: drop irrelevant entries (one warning with the
    count), drop competitors not grounded in evidence or in the founder's words, remove a
    website that is not the competitor's own, check sourced pricing, then merge duplicates.

    Returns the competitors, a map from every kept draft's normalised name to the name it was
    merged into (so comparison rows can follow the merge), and the warnings.
    """
    warnings: list[str] = []
    irrelevant = [draft for draft in drafts if _irrelevant(draft)]
    if irrelevant:
        warnings.append(f"competitors: dropped {len(irrelevant)} with no type or relevance note")

    grounded: list[CompetitorDraft] = []
    for index, draft in enumerate(drafts):
        if draft in irrelevant:
            continue
        label = f"competitors[{index}]"
        problem = _grounding_problem(draft.name, draft.basis, draft.source_ids, evidence, founder)
        if problem:
            warnings.append(f"{label}: removed {draft.name!r}; {problem}")
            continue
        if draft.website:
            reason = _website_problem(draft, evidence)
            if reason:
                warnings.append(f"{label}.website: removed {draft.website!r}; {reason}")
                draft = draft.model_copy(update={"website": None})
        draft, found = _check_pricing(draft, evidence, label)
        warnings += found
        grounded.append(draft)

    merged: list[CompetitorDraft] = []
    names: dict[str, str] = {}
    for draft in grounded:
        twin = next((index for index, other in enumerate(merged) if _same_competitor(other, draft)), None)
        if twin is None:
            merged.append(draft)
            names[name_key(draft.name)] = draft.name
            continue
        warnings.append(f"competitors: merged a duplicate {draft.name!r} into {merged[twin].name!r}")
        merged[twin] = _merge(merged[twin], draft)
        names[name_key(draft.name)] = merged[twin].name

    competitors = [
        Competitor(**dict(draft), info_completeness=completeness(draft)) for draft in merged
    ]
    return competitors, names, warnings


# --- comparison matrix ------------------------------------------------------------------------


def feature_key(feature: str) -> str:
    return " ".join(feature.split()).casefold()


def comparison_features(idea_features: list[str], draft: ComparisonDraft, competitors: list[Competitor]) -> list[str]:
    """Section 8.3, "the idea's key_features plus features seen in competitor data (cap 8)":
    the idea's features first, then the features the model listed that a competitor's key
    features also name, then any remaining competitor key feature, up to
    COMPARISON_FEATURES_MAX. A feature the model invented, which neither the idea nor any
    competitor names, is left out."""
    in_data: dict[str, str] = {}
    for competitor in competitors:
        for feature in competitor.key_features:
            in_data.setdefault(feature_key(feature), feature)
    from_idea = {feature_key(feature) for feature in idea_features}
    features: list[str] = []
    chosen: set[str] = set()
    for feature in [*idea_features, *draft.features, *in_data.values()]:
        key = feature_key(feature)
        if key in chosen or (key not in from_idea and key not in in_data):
            continue
        features.append(feature)
        chosen.add(key)
    return features[:COMPARISON_FEATURES_MAX]


def _cell_backed(cell: ComparisonCell, competitor: Competitor, evidence: list[EvidenceItem]) -> bool:
    """evidence_found needs a real cited source that names this competitor."""
    return named_in_sources(competitor.name, cell.source_ids, evidence)


def build_comparison(
    draft: ComparisonDraft,
    competitors: list[Competitor],
    names: dict[str, str],
    idea_features: list[str],
    evidence: list[EvidenceItem],
) -> tuple[Comparison, list[str]]:
    """One row per competitor and one cell per feature. A cell the model left out is unclear;
    a cell marked evidence_found without a cited source naming the competitor becomes unclear.
    feature_coverage is then counted from the rows."""
    features = comparison_features(idea_features, draft, competitors)
    by_competitor: dict[str, dict[str, ComparisonCell]] = {competitor.name: {} for competitor in competitors}
    for row in draft.rows:
        owner = names.get(name_key(row.competitor))
        if owner not in by_competitor:
            continue
        cells = by_competitor[owner]
        for cell in row.cells:
            key = feature_key(cell.feature)
            if key not in cells or CELL_RANK[cell.status] > CELL_RANK[cells[key].status]:
                cells[key] = cell

    rows: list[ComparisonRow] = []
    demoted = 0
    for competitor in competitors:
        cells = []
        for feature in features:
            cell = by_competitor[competitor.name].get(feature_key(feature))
            if cell is None:
                cells.append(ComparisonCell(feature=feature, status="unclear"))
                continue
            status = cell.status
            if status == "evidence_found" and not _cell_backed(cell, competitor, evidence):
                status, demoted = "unclear", demoted + 1
            cells.append(ComparisonCell(feature=feature, status=status, source_ids=cell.source_ids))
        rows.append(ComparisonRow(competitor=competitor.name, cells=cells))

    coverage = [
        FeatureCoverage(
            feature=feature,
            competitors_with_evidence=sum(row.cells[index].status == "evidence_found" for row in rows),
        )
        for index, feature in enumerate(features)
    ]
    warnings = []
    if demoted:
        warnings.append(
            f"comparison: {demoted} cell(s) marked evidence_found had no cited source naming the competitor, "
            "so they are now unclear"
        )
    return Comparison(features=features, rows=rows, feature_coverage=coverage), warnings


def _feature_words(feature: str) -> set[str]:
    return {word for word in _tokens(feature) if len(word) >= FEATURE_WORD_MIN_CHARS and word not in STOP_WORDS}


def feature_sources(feature: str, competitor: Competitor, evidence: list[EvidenceItem]) -> list[str]:
    words = _feature_words(feature)
    if not words:
        return []
    return [
        item.id
        for item in cited_items(competitor.source_ids, evidence)
        if named_in_sources(competitor.name, [item.id], evidence) and words <= set(_tokens(f"{item.title} {item.snippet}"))
    ]


def _coverage(features: list[str], rows: list[ComparisonRow]) -> list[FeatureCoverage]:
    return [
        FeatureCoverage(
            feature=feature,
            competitors_with_evidence=sum(
                cell.feature == feature and cell.status == "evidence_found" for row in rows for cell in row.cells
            ),
        )
        for feature in features
    ]


def align_key_features(
    competitors: list[Competitor], comparison: Comparison, evidence: list[EvidenceItem]
) -> tuple[list[Competitor], Comparison, list[str]]:
    rows = {row.competitor: row for row in comparison.rows}
    aligned: list[Competitor] = []
    changed_rows: dict[str, ComparisonRow] = {}
    warnings: list[str] = []
    for index, competitor in enumerate(competitors):
        row = rows.get(competitor.name)
        cells = list(row.cells) if row is not None else []
        position = {feature_key(cell.feature): at for at, cell in enumerate(cells)}
        kept: list[str] = []
        for feature in competitor.key_features:
            at = position.get(feature_key(feature))
            if at is None or cells[at].status == "evidence_found":
                kept.append(feature)
                continue
            shown = {"feature": feature, "name": competitor.name, "status": cells[at].status}
            backed = feature_sources(feature, competitor, evidence)
            if backed:
                cells[at] = ComparisonCell(feature=cells[at].feature, status="evidence_found", source_ids=backed)
                kept.append(feature)
                warnings.append(f"comparison: {FEATURE_TABLE_CORRECTED.format(**shown)}")
            else:
                warnings.append(f"competitors[{index}].key_features: {FEATURE_REMOVED.format(**shown)}")
        if kept != list(competitor.key_features):
            competitor = competitor.model_copy(update={"key_features": kept})
            competitor = competitor.model_copy(update={"info_completeness": completeness(competitor)})
        if row is not None and cells != list(row.cells):
            changed_rows[row.competitor] = ComparisonRow(competitor=row.competitor, cells=cells)
        aligned.append(competitor)
    if not warnings:
        return competitors, comparison, []
    new_rows = [changed_rows.get(row.competitor, row) for row in comparison.rows]
    fixed = Comparison(features=comparison.features, rows=new_rows, feature_coverage=_coverage(comparison.features, new_rows))
    return aligned, fixed, warnings


# --- market gaps -----------------------------------------------------------------------------


def check_gaps(
    gaps: list[MarketGapDraft], comparison: Comparison, competitor_count: int
) -> tuple[list[MarketGap], list[str]]:
    """Gaps are hypotheses (Section 2 rule 5). Code caps confidence at medium, sets the fixed
    caveat, keeps only related features that are in the comparison, and drops a gap the matrix
    contradicts: one whose related features each have evidence for more than half of the
    competitors."""
    coverage = {feature_key(item.feature): item.competitors_with_evidence for item in comparison.feature_coverage}
    names = {feature_key(feature): feature for feature in comparison.features}
    kept: list[MarketGap] = []
    warnings: list[str] = []
    for index, gap in enumerate(gaps):
        label = f"market_gaps[{index}]"
        related = [names[feature_key(feature)] for feature in gap.related_features if feature_key(feature) in names]
        unknown = [feature for feature in gap.related_features if feature_key(feature) not in names]
        if unknown:
            warnings.append(f"{label}: removed related features that are not in the comparison: {', '.join(unknown)}")
        if related and all(coverage[feature_key(feature)] * 2 > competitor_count for feature in related):
            warnings.append(f"{label}: removed; the comparison shows evidence for its features at most competitors")
            continue
        confidence = gap.confidence
        if confidence == "high":
            confidence = "medium"
            warnings.append(f"{label}: confidence lowered from high to medium; a gap is a hypothesis")
        kept.append(
            MarketGap(**{**dict(gap), "related_features": related, "confidence": confidence, "caveat": COMPETITOR_CAVEAT})
        )
    return kept, warnings
