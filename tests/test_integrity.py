"""Evidence-integrity checks and repairs (KIRO_PROMPT_M2.md Section 5.4).

The real Market and Competitor result schemas arrive in Tasks 1 and 2. These stand-in models
use the field names fixed in the specification so the checks are exercised end to end now.
"""

import json
from typing import Literal

import pytest
from pydantic import BaseModel

from agents import integrity
from agents.evidence import build_evidence
from models.schemas import Basis, LabeledItem, MarketFigure, MarketOpportunityResult, QuantEstimate, SourceRef
from tests.m2_fakes import EVIDENCE, MARKET_SEARCH, evidence_item, market_reply


class Segment(BaseModel):
    name: str
    pain_points: list[LabeledItem] = []


class MarketSize(BaseModel):
    tam: QuantEstimate


class MarketLike(BaseModel):
    developments: list[LabeledItem] = []
    market_size: MarketSize
    segments: list[Segment] = []
    sources: list[SourceRef] = []
    caveats: list[str] = []


class CompetitorLike(BaseModel):
    name: str
    type: Literal["direct", "indirect", "emerging"]
    website: str | None = None
    source_ids: list[str] = []
    basis: Literal["sourced", "user_provided"] = "sourced"
    pricing_model: QuantEstimate = QuantEstimate(status="unavailable")
    strengths: list[LabeledItem] = []
    weaknesses: list[LabeledItem] = []


class GapLike(BaseModel):
    description: str
    basis: Basis
    source_ids: list[str] = []
    confidence: Literal["low", "medium"] = "low"
    caveat: str = ""


class CompetitorResultLike(BaseModel):
    competitors: list[CompetitorLike] = []
    market_gaps: list[GapLike] = []
    sources: list[SourceRef] = []
    caveats: list[str] = []


def labeled(basis: str = "sourced", *ids: str, text: str = "Demand is rising") -> LabeledItem:
    return LabeledItem(text=text, basis=basis, source_ids=list(ids))


def clean_market() -> MarketLike:
    return MarketLike(
        developments=[labeled("sourced", "S1")],
        market_size=MarketSize(tam=QuantEstimate(value="10,000 farmers", status="sourced", source_ids=["S2"])),
        segments=[Segment(name="Small farmers", pain_points=[labeled("assumption")])],
        sources=[SourceRef(id="S1", title="LeafDoc", url="https://leafdoc.example/pricing")],
        caveats=[integrity.MARKET_CAVEAT],
    )


def clean_competitors() -> CompetitorResultLike:
    return CompetitorResultLike(
        competitors=[
            CompetitorLike(name="LeafDoc", type="direct", website="https://leafdoc.example", source_ids=["S1"]),
            CompetitorLike(name="Founder's rival", type="indirect", basis="user_provided"),
        ],
        market_gaps=[
            GapLike(description="No offline mode seen", basis="ai_interpretation", caveat=integrity.COMPETITOR_CAVEAT)
        ],
        caveats=[integrity.COMPETITOR_CAVEAT],
    )


# --- URL and domain utilities -------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.LeafDoc.example/pricing", "leafdoc.example"),
        ("leafdoc.example", "leafdoc.example"),
        ("http://app.leafdoc.example:8080/x", "app.leafdoc.example"),
        ("", ""),
    ],
)
def test_domain_of(raw: str, expected: str) -> None:
    assert integrity.domain_of(raw) == expected


def test_url_in_evidence_normalises_but_rejects_foreign_urls() -> None:
    assert integrity.url_in_evidence("https://leafdoc.example/pricing/", EVIDENCE)
    assert integrity.url_in_evidence("HTTPS://LeafDoc.example/pricing", EVIDENCE)
    assert integrity.url_in_evidence("https://cropsense.example/about", EVIDENCE)
    assert not integrity.url_in_evidence("https://leafdoc.example/other", EVIDENCE)
    assert not integrity.url_in_evidence("", EVIDENCE)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("https://leafdoc.example", True),
        ("leafdoc.example", True),
        ("https://app.leafdoc.example", True),
        ("https://www.cropsense.example", True),
        ("https://leafdoc.example.evil.net", False),
        ("https://notleafdoc.example", False),
        ("", False),
    ],
)
def test_domain_in_evidence_rejects_look_alikes(candidate: str, expected: bool) -> None:
    assert integrity.domain_in_evidence(candidate, EVIDENCE) is expected


# --- source ids ---------------------------------------------------------------


def test_valid_and_supporting_source_ids() -> None:
    ids = ["s1", " S2 ", "S9", "S1", "S0"]
    assert integrity.valid_source_ids(ids, EVIDENCE) == ["S1", "S2", "S0"]
    assert integrity.supporting_source_ids(ids, EVIDENCE) == ["S1", "S2"]
    assert integrity.supporting_source_ids(["S0"], EVIDENCE) == []


# --- repairs ------------------------------------------------------------------


def test_unknown_source_id_is_dropped_with_a_warning() -> None:
    fixed, warnings = integrity.repair_tree(labeled("sourced", "S1", "S9"), EVIDENCE)
    assert fixed.source_ids == ["S1"] and fixed.basis is Basis.sourced
    assert len(warnings) == 1 and "S9" in warnings[0]


@pytest.mark.parametrize("ids", [("S9",), ("S0",)])
def test_sourced_claim_without_valid_support_is_downgraded(ids: tuple[str, ...]) -> None:
    item = labeled("sourced", *ids)
    fixed, warnings = integrity.repair_tree(item, EVIDENCE)
    assert fixed.basis is Basis.ai_interpretation
    assert any("AI interpretation" in w for w in warnings)
    assert item.basis is Basis.sourced, "the input must not be mutated"


def test_non_sourced_items_are_left_alone() -> None:
    item = labeled("assumption")
    fixed, warnings = integrity.repair_tree(item, EVIDENCE)
    assert fixed is item and warnings == []


def test_sourced_figure_repairs() -> None:
    no_source, w1 = integrity.repair_tree(QuantEstimate(value="USD 9 billion", status="sourced", source_ids=["S9"]), EVIDENCE)
    assert (no_source.status, no_source.value) == ("unavailable", None) and w1
    summary_only, w2 = integrity.repair_tree(QuantEstimate(value="USD 2 billion", status="sourced", source_ids=["S0"]), EVIDENCE)
    assert (summary_only.status, summary_only.value) == ("estimate_needs_verification", "USD 2 billion") and w2
    good, w3 = integrity.repair_tree(QuantEstimate(value="10,000", status="sourced", source_ids=["S2"]), EVIDENCE)
    assert good.status == "sourced" and w3 == []


def test_unverifiable_website_is_set_to_none() -> None:
    fake, warnings = integrity.repair_tree(
        CompetitorLike(name="Ghost", type="direct", website="https://ghost.example", source_ids=["S1"]), EVIDENCE
    )
    assert fake.website is None and "ghost.example" in warnings[0]
    real, none = integrity.repair_tree(
        CompetitorLike(name="LeafDoc", type="direct", website="https://leafdoc.example", source_ids=["S1"]), EVIDENCE
    )
    assert real.website == "https://leafdoc.example" and none == []


def test_competitor_basis_is_not_downgraded_by_the_generic_repair() -> None:
    """Section 8.3: a competitor with no source is dropped by the agent, never relabelled."""
    fixed, _ = integrity.repair_tree(CompetitorLike(name="Ghost", type="direct", source_ids=["S9"]), EVIDENCE)
    assert fixed.basis == "sourced" and fixed.source_ids == []
    assert integrity.find_violations(fixed, EVIDENCE)


def test_nested_repairs_report_their_path_and_leave_a_clean_result() -> None:
    market = clean_market().model_copy(
        update={"segments": [Segment(name="Small farmers", pain_points=[labeled("sourced", "S7")])]}
    )
    fixed, warnings = integrity.repair_tree(market, EVIDENCE)
    assert any(w.startswith("segments[0].pain_points[0]") for w in warnings)
    assert fixed.segments[0].pain_points[0].basis is Basis.ai_interpretation
    assert integrity.check_market_integrity(fixed, EVIDENCE) == []


# --- checks -------------------------------------------------------------------


def test_clean_results_have_no_violations() -> None:
    assert integrity.check_market_integrity(clean_market(), EVIDENCE) == []
    assert integrity.check_competitor_integrity(clean_competitors(), EVIDENCE) == []


def test_violations_for_unknown_ids_unsupported_claims_and_foreign_urls() -> None:
    market = clean_market().model_copy(
        update={
            "developments": [labeled("sourced", "S9")],
            "sources": [SourceRef(id="S1", title="Made up", url="https://invented.example/report")],
        }
    )
    problems = integrity.check_market_integrity(market, EVIDENCE)
    assert any("unknown source id 'S9'" in p for p in problems)
    assert any("sourced claim has no valid source" in p for p in problems)
    assert any("invented.example" in p for p in problems)


def test_urls_inside_text_must_come_from_the_evidence() -> None:
    bad = labeled("assumption", text="See https://invented.example/page.")
    good = labeled("assumption", text="See https://leafdoc.example/pricing.")
    assert any("invented.example/page" in p for p in integrity.find_violations(bad, EVIDENCE))
    assert integrity.find_violations(good, EVIDENCE) == []


def test_empty_names_and_text_are_violations() -> None:
    market = clean_market().model_copy(update={"segments": [Segment(name="  ")]})
    assert any("segments[0].name: is empty" in p for p in integrity.check_market_integrity(market, EVIDENCE))


def test_invalid_enum_values_are_violations() -> None:
    broken = labeled("assumption").model_copy(update={"basis": "guess"})
    market = clean_market().model_copy(update={"developments": [broken]})
    assert any("developments" in p for p in integrity.check_market_integrity(market, EVIDENCE))


def test_figure_marked_sourced_without_support_is_a_violation() -> None:
    market = clean_market().model_copy(
        update={"market_size": MarketSize(tam=QuantEstimate(value="USD 3 billion", status="sourced", source_ids=["S0"]))}
    )
    assert any("figure marked sourced" in p for p in integrity.check_market_integrity(market, EVIDENCE))


def test_required_caveats_are_enforced() -> None:
    market = clean_market().model_copy(update={"caveats": []})
    assert any("required caveat" in p for p in integrity.check_market_integrity(market, EVIDENCE))
    competitors = clean_competitors().model_copy(update={"caveats": []})
    assert any("required caveat" in p for p in integrity.check_competitor_integrity(competitors, EVIDENCE))


def test_every_gap_needs_a_caveat_and_at_most_medium_confidence() -> None:
    overconfident = GapLike(description="Gap", basis="ai_interpretation", caveat="").model_copy(
        update={"confidence": "high"}
    )
    result = clean_competitors().model_copy(update={"market_gaps": [overconfident]})
    problems = integrity.check_competitor_integrity(result, EVIDENCE)
    assert any("market_gaps[0].caveat" in p for p in problems)
    assert any("must be low or medium" in p for p in problems)


def test_competitor_checks_for_websites_and_missing_sources() -> None:
    result = clean_competitors().model_copy(
        update={
            "competitors": [
                CompetitorLike(name="Ghost", type="direct", website="https://ghost.example", source_ids=[]),
                CompetitorLike(name="Founder's rival", type="indirect", basis="user_provided"),
            ]
        }
    )
    problems = integrity.check_competitor_integrity(result, EVIDENCE)
    assert any("ghost.example" in p for p in problems)
    assert any("competitors[0]: sourced claim has no valid source" in p for p in problems)
    assert not any("competitors[1]" in p for p in problems), "a founder-named competitor needs no source"


def test_repairing_then_checking_a_competitor_result() -> None:
    result = clean_competitors().model_copy(
        update={"competitors": [CompetitorLike(name="LeafDoc", type="direct", website="https://fake.example", source_ids=["S1", "S8"])]}
    )
    fixed, warnings = integrity.repair_tree(result, EVIDENCE)
    assert fixed.competitors[0].website is None and fixed.competitors[0].source_ids == ["S1"]
    assert len(warnings) == 2
    assert integrity.check_competitor_integrity(fixed, EVIDENCE) == []


# --- review fixes: M1 malformed URLs ----------------------------------------

MALFORMED_URLS = ["https://[bad", "http://[::1", "https://ex\uff0fample.com/x", "[click](https://x.example)"]


@pytest.mark.parametrize("bad", MALFORMED_URLS)
def test_malformed_urls_never_raise_and_never_match(bad: str) -> None:
    assert integrity.domain_of(bad) == ""
    assert integrity.normalize_url(bad) == ""
    assert integrity.url_in_evidence(bad, EVIDENCE) is False
    assert integrity.domain_in_evidence(bad, EVIDENCE) is False


@pytest.mark.parametrize("bad", MALFORMED_URLS)
def test_malformed_llm_urls_cannot_crash_repair_or_checks(bad: str) -> None:
    competitor = CompetitorLike(name="LeafDoc", type="direct", website=bad, source_ids=["S1"])
    fixed, warnings = integrity.repair_tree(competitor, EVIDENCE)
    assert fixed.website is None and warnings
    result = clean_competitors().model_copy(
        update={
            "competitors": [competitor],
            "sources": [SourceRef(id="S1", title="LeafDoc", url=bad)],
        }
    )
    problems = integrity.check_competitor_integrity(result, EVIDENCE)
    assert any("website" in p for p in problems)
    assert any("sources[0]" in p for p in problems)
    market = clean_market().model_copy(update={"developments": [labeled("assumption", text=f"See {bad} now")]})
    assert isinstance(integrity.check_market_integrity(market, EVIDENCE), list)


# --- review fixes: M2 figures need evidence ---------------------------------


def test_uncited_estimate_is_repaired_to_unavailable() -> None:
    estimate = QuantEstimate(value="USD 50 billion", status="estimate_needs_verification")
    assert any("cites no valid evidence" in p for p in integrity.find_violations(estimate, EVIDENCE))
    fixed, warnings = integrity.repair_tree(estimate, EVIDENCE)
    assert (fixed.status, fixed.value) == ("unavailable", None)
    assert len(warnings) == 1 and "estimated figure cited no evidence" in warnings[0]
    assert integrity.find_violations(fixed, EVIDENCE) == []


def test_estimate_citing_only_unknown_ids_is_repaired_with_two_warnings() -> None:
    fixed, warnings = integrity.repair_tree(
        QuantEstimate(value="USD 4 billion", status="estimate_needs_verification", source_ids=["S9"]), EVIDENCE
    )
    assert (fixed.status, fixed.value, fixed.source_ids) == ("unavailable", None, [])
    assert len(warnings) == 2


@pytest.mark.parametrize("ids", [["S0"], ["S1"]])
def test_cited_estimates_are_kept(ids: list[str]) -> None:
    estimate = QuantEstimate(value="USD 2 billion", status="estimate_needs_verification", source_ids=ids)
    fixed, warnings = integrity.repair_tree(estimate, EVIDENCE)
    assert fixed == estimate and warnings == []
    assert integrity.find_violations(estimate, EVIDENCE) == []


def test_unavailable_figure_never_keeps_a_value() -> None:
    contradictory = QuantEstimate(value="USD 7 billion", status="unavailable")
    problems = integrity.find_violations(contradictory, EVIDENCE)
    assert any("unavailable figure must have no value" in p for p in problems)
    fixed, warnings = integrity.repair_tree(contradictory, EVIDENCE)
    assert (fixed.status, fixed.value) == ("unavailable", None) and len(warnings) == 1
    assert integrity.find_violations(fixed, EVIDENCE) == []


def test_figures_without_a_value_need_no_source() -> None:
    for status in ("estimate_needs_verification", "unavailable"):
        empty = QuantEstimate(value=None, status=status)
        assert integrity.repair_tree(empty, EVIDENCE) == (empty, [])
        assert integrity.find_violations(empty, EVIDENCE) == []


def test_invented_pricing_inside_a_competitor_is_removed() -> None:
    competitor = CompetitorLike(
        name="LeafDoc",
        type="direct",
        source_ids=["S1"],
        pricing_model=QuantEstimate(value="USD 99 a month", status="estimate_needs_verification"),
    )
    fixed, warnings = integrity.repair_tree(competitor, EVIDENCE)
    assert (fixed.pricing_model.status, fixed.pricing_model.value) == ("unavailable", None)
    assert any(w.startswith("pricing_model") for w in warnings)


# --- review fixes: M3 strengths and weaknesses need sources -----------------


def test_unsourced_strengths_and_weaknesses_are_violations_whatever_their_basis() -> None:
    competitor = CompetitorLike(
        name="LeafDoc",
        type="direct",
        source_ids=["S1"],
        strengths=[labeled("assumption", text="Cheapest app"), labeled("sourced", "S1", text="Low price")],
        weaknesses=[labeled("ai_interpretation", "S0", text="Slow support")],
    )
    result = clean_competitors().model_copy(update={"competitors": [competitor]})
    problems = integrity.check_competitor_integrity(result, EVIDENCE)
    assert "competitors[0].strengths[0]: has no valid source" in problems
    assert "competitors[0].weaknesses[0]: has no valid source" in problems
    assert not any("strengths[1]" in p for p in problems)


def test_unsupported_strengths_and_weaknesses_are_removed_not_relabelled() -> None:
    competitor = CompetitorLike(
        name="LeafDoc",
        type="direct",
        source_ids=["S1"],
        strengths=[labeled("sourced", "S9", text="Best accuracy"), labeled("sourced", "S1", text="Low price")],
        weaknesses=[labeled("assumption", text="Hard to use")],
    )
    fixed, warnings = integrity.repair_tree(competitor, EVIDENCE)
    assert [s.text for s in fixed.strengths] == ["Low price"]
    assert fixed.weaknesses == []
    assert sum("removed strength" in w for w in warnings) == 1
    assert sum("removed weakness" in w for w in warnings) == 1
    result = clean_competitors().model_copy(update={"competitors": [fixed]})
    assert integrity.check_competitor_integrity(result, EVIDENCE) == []


# --- review fixes: L2 listed sources must match the evidence ----------------


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (SourceRef(id="S9", title="t", url="https://leafdoc.example/pricing"), "unknown source id 'S9'"),
        (SourceRef(id="S1", title="t", url="https://news.example/agritech-2026"), "does not match evidence item S1"),
        (SourceRef(id="S0", title="summary", url=""), "search summary S0 cannot be listed as a source"),
        (SourceRef(id="S1", title="t", url=""), "does not match evidence item S1"),
    ],
)
def test_listed_sources_are_checked_against_the_evidence(ref: SourceRef, expected: str) -> None:
    problems = integrity.find_violations(ref, EVIDENCE)
    assert len(problems) == 1 and expected in problems[0]


def test_a_matching_source_passes_even_with_url_variants() -> None:
    for url in ("https://leafdoc.example/pricing", "https://www.leafdoc.example/pricing/", "s1-ignored"):
        ref = SourceRef(id="s1", title="LeafDoc", url=url)
        assert (integrity.find_violations(ref, EVIDENCE) == []) is (url != "s1-ignored")


# --- review fixes: L7 empty websites ----------------------------------------


@pytest.mark.parametrize("empty", ["", "   "])
def test_empty_website_becomes_none_with_one_warning(empty: str) -> None:
    """Section 5.4 lists "set an unverifiable website to null" as a repair, and every repair
    gets a warning, so an empty website is repaired and reported exactly once."""
    competitor = CompetitorLike(name="LeafDoc", type="direct", website=empty, source_ids=["S1"])
    assert any("website" in p for p in integrity.find_violations(competitor, EVIDENCE))
    fixed, warnings = integrity.repair_tree(competitor, EVIDENCE)
    assert fixed.website is None
    assert warnings == ["website: replaced an empty website with null"]
    assert integrity.find_violations(fixed, EVIDENCE) == []


def test_urls_need_a_scheme_while_domain_matching_accepts_bare_domains() -> None:
    assert integrity.normalize_url("leafdoc.example/pricing") == ""
    assert integrity.normalize_url("javascript:alert(1)") == ""
    assert not integrity.url_in_evidence("leafdoc.example/pricing", EVIDENCE)
    assert integrity.domain_in_evidence("leafdoc.example", EVIDENCE)
    assert not integrity.website_in_evidence("leafdoc.example", EVIDENCE), "a website must be a full http(s) URL"


def test_an_unsupported_sourced_strength_is_reported_once() -> None:
    competitor = CompetitorLike(
        name="LeafDoc", type="direct", source_ids=["S1"], strengths=[labeled("sourced", "S0", text="Market leader")]
    )
    result = clean_competitors().model_copy(update={"competitors": [competitor]})
    problems = [p for p in integrity.check_competitor_integrity(result, EVIDENCE) if "strengths[0]" in p]
    assert problems == ["competitors[0].strengths[0]: sourced claim has no valid source"]


def test_each_figure_problem_is_reported_once() -> None:
    contradictory = QuantEstimate(value="USD 7 billion", status="unavailable")
    assert integrity.find_violations(contradictory, EVIDENCE) == [
        "QuantEstimate: an unavailable figure must have no value"
    ]


# --- final Stage 1 correction: websites must be http(s) URLs on an evidence domain ---

UNSAFE_WEBSITES = [
    ("javascript://leafdoc.example/%0aalert(1)", "not a valid http or https URL"),
    ("javascript:alert(1)", "not a valid http or https URL"),
    ("data:text/html,<script>alert(1)</script>", "not a valid http or https URL"),
    ("ftp://leafdoc.example/files", "not a valid http or https URL"),
    ("leafdoc.example", "not a valid http or https URL"),
    ("//leafdoc.example", "not a valid http or https URL"),
    ("https:///leafdoc.example", "not a valid http or https URL"),
    ("https://leafdoc.example/a b", "not a valid http or https URL"),
    ("https://leafdoc.example/\nalert", "not a valid http or https URL"),
    ("https://leafdoc.example@evil.example", "matches no evidence domain"),
    ("https://leafdoc.example.evil.net", "matches no evidence domain"),
]


@pytest.mark.parametrize(("website", "reason"), UNSAFE_WEBSITES)
def test_only_http_or_https_websites_on_an_evidence_domain_are_accepted(website: str, reason: str) -> None:
    competitor = CompetitorLike(name="LeafDoc", type="direct", website=website, source_ids=["S1"])
    assert not integrity.website_in_evidence(website, EVIDENCE)
    problems = integrity.find_violations(competitor, EVIDENCE)
    assert len(problems) == 1 and reason in problems[0]
    fixed, warnings = integrity.repair_tree(competitor, EVIDENCE)
    assert fixed.website is None
    assert len(warnings) == 1 and reason in warnings[0]
    assert "\n" not in warnings[0]
    assert integrity.find_violations(fixed, EVIDENCE) == []


def test_a_matching_host_does_not_rescue_a_non_http_scheme() -> None:
    for website in ("javascript://leafdoc.example/%0aalert(1)", "ftp://leafdoc.example/files"):
        assert integrity.domain_in_evidence(website, EVIDENCE), "the host matches evidence"
        assert not integrity.website_in_evidence(website, EVIDENCE), "but the scheme is not http(s)"


@pytest.mark.parametrize(
    "website",
    [
        "https://leafdoc.example",
        "http://leafdoc.example/about",
        "HTTPS://LeafDoc.example/",
        "https://app.leafdoc.example",
        "https://www.cropsense.example",
    ],
)
def test_http_and_https_websites_on_evidence_domains_are_kept(website: str) -> None:
    competitor = CompetitorLike(name="LeafDoc", type="direct", website=website, source_ids=["S1"])
    assert integrity.website_in_evidence(website, EVIDENCE)
    assert integrity.find_violations(competitor, EVIDENCE) == []
    assert integrity.repair_tree(competitor, EVIDENCE) == (competitor, [])


# --- final Stage 1 correction: S0 never backs a URL, a website or a source -----


def test_the_search_summary_never_backs_a_url_a_website_or_a_source() -> None:
    """Section 5.1: S0 has no source URL. Even an S0 item wrongly built with a URL must not make
    that URL, domain or website valid, and S0 is never a listed source, whatever its URL."""
    tampered = [evidence_item("S0", "https://summary.example/page", "Summary text."), *EVIDENCE[1:]]
    assert not integrity.url_in_evidence("https://summary.example/page", tampered)
    assert not integrity.domain_in_evidence("summary.example", tampered)
    assert not integrity.website_in_evidence("https://summary.example", tampered)
    for url in ("https://summary.example/page", "https://leafdoc.example/pricing", ""):
        ref = SourceRef(id="S0", title="Search engine summary", url=url)
        assert integrity.find_violations(ref, tampered) == [
            "SourceRef: the search summary S0 cannot be listed as a source"
        ]


# --- final Stage 1 correction: figure rules from Sections 5.1, 7.2 and 8.4 -----


@pytest.mark.parametrize(
    ("status", "ids", "value", "expected_status", "expected_value", "warning_count"),
    [
        # 7.2: a sourced figure whose number appears in a cited snippet is kept.
        ("sourced", ["S2"], "10,000", "sourced", "10,000", 0),
        # 5.1: resting only on S0 is never sourced; 7.2 downgrade keeps the figure.
        ("sourced", ["S0"], "USD 2 billion", "estimate_needs_verification", "USD 2 billion", 1),
        ("sourced", ["S0", "S9"], "USD 2 billion", "estimate_needs_verification", "USD 2 billion", 2),
        # Nothing to keep: a sourced status without a figure becomes unavailable.
        ("sourced", ["S0"], None, "unavailable", None, 1),
        # 7.2: "If it cites nothing, set unavailable."
        ("sourced", [], "USD 9 billion", "unavailable", None, 1),
        # An estimate keeps its figure only while it cites evidence.
        ("estimate_needs_verification", ["S0"], "USD 2 billion", "estimate_needs_verification", "USD 2 billion", 0),
        ("estimate_needs_verification", ["S1"], "USD 2 billion", "estimate_needs_verification", "USD 2 billion", 0),
        ("estimate_needs_verification", [], "USD 50 billion", "unavailable", None, 1),
        # 8.4: unknown means null with a status.
        ("unavailable", [], None, "unavailable", None, 0),
        ("unavailable", ["S1"], "USD 7 billion", "unavailable", None, 1),
    ],
)
def test_figure_rules_follow_the_specification(
    status: str, ids: list[str], value: str | None, expected_status: str, expected_value: str | None, warning_count: int
) -> None:
    fixed, warnings = integrity.repair_tree(QuantEstimate(value=value, status=status, source_ids=ids), EVIDENCE)
    assert (fixed.status, fixed.value) == (expected_status, expected_value)
    assert len(warnings) == warning_count
    assert integrity.find_violations(fixed, EVIDENCE) == []


# --- Task 1 addition: links in free text must come from the evidence ---------------


def test_foreign_links_in_text_are_replaced_and_evidence_links_kept() -> None:
    market = clean_market().model_copy(
        update={"developments": [labeled("assumption", text="See https://invented.example/a, then https://leafdoc.example/pricing.")]}
    )
    assert any("invented.example" in p for p in integrity.check_market_integrity(market, EVIDENCE))
    fixed, warnings = integrity.remove_foreign_urls(market, EVIDENCE)
    assert fixed.developments[0].text == f"See {integrity.LINK_REMOVED}, then https://leafdoc.example/pricing."
    assert warnings == ["developments[0].text: removed 1 link(s) that are not in the search evidence"]
    assert integrity.check_market_integrity(fixed, EVIDENCE) == []


def test_link_removal_covers_text_lists_and_leaves_sources_and_labels_alone() -> None:
    market = clean_market().model_copy(update={"caveats": [integrity.MARKET_CAVEAT, "Ask https://invented.example/b"]})
    fixed, warnings = integrity.remove_foreign_urls(market, EVIDENCE)
    assert fixed.caveats == [integrity.MARKET_CAVEAT, f"Ask {integrity.LINK_REMOVED}"]
    assert len(warnings) == 1
    assert fixed.sources == market.sources
    assert fixed.developments[0].basis is Basis.sourced


def test_link_removal_returns_the_same_model_when_nothing_changes() -> None:
    market = clean_market()
    assert integrity.remove_foreign_urls(market, EVIDENCE) == (market, [])


# --- Task 1 scope fixes ----------------------------------------------------------------------


class WithBroaderMarkets(BaseModel):
    broader_markets: list[MarketFigure] = []


def test_figures_in_broader_markets_are_checked_and_repaired_like_any_figure() -> None:
    model = WithBroaderMarkets(
        broader_markets=[MarketFigure(value="USD 2 billion", status="sourced", source_ids=["S9"], scope="broader_market")]
    )
    problems = integrity.find_violations(model, EVIDENCE)
    assert any("unknown source id 'S9'" in p for p in problems)
    assert any("figure marked sourced has no valid source" in p for p in problems)
    fixed, warnings = integrity.repair_tree(model, EVIDENCE)
    figure = fixed.broader_markets[0]
    assert (figure.status, figure.value, figure.source_ids) == ("unavailable", None, []) and len(warnings) == 2


@pytest.mark.parametrize("scope", [None, "broader_market"])
def test_a_tam_for_a_broader_or_unknown_market_is_a_violation(scope: str | None) -> None:
    market = MarketOpportunityResult(**json.loads(market_reply()), caveats=[integrity.MARKET_CAVEAT])
    evidence = build_evidence(MARKET_SEARCH)
    assert integrity.check_market_integrity(market, evidence) == []
    tam = market.market_size.tam.model_copy(update={"scope": scope})
    wrong = market.model_copy(update={"market_size": market.market_size.model_copy(update={"tam": tam})})
    assert integrity.check_market_integrity(wrong, evidence) == [
        "market_size.tam: a figure for a broader or unknown market cannot be the TAM"
    ]


def test_an_unavailable_slot_needs_no_scope() -> None:
    market = MarketOpportunityResult(**json.loads(market_reply()), caveats=[integrity.MARKET_CAVEAT])
    assert market.market_size.sam.scope is None and market.market_size.sam.status == "unavailable"
    assert integrity.check_market_integrity(market, build_evidence(MARKET_SEARCH)) == []


# --- Task 2: the real competitor result and its comparison matrix ------------------------------


def real_competitors(status: str = "evidence_found", ids: list[str] | None = None, counted: int | None = None):
    from models.schemas import (
        Comparison,
        ComparisonCell,
        ComparisonRow,
        Competitor,
        CompetitorAnalysisResult,
        DataQuality,
        FeatureCoverage,
    )

    ids = ["S1"] if ids is None else ids
    found = 1 if status == "evidence_found" else 0
    return CompetitorAnalysisResult(
        competitors=[
            Competitor(name="LeafDoc", type="direct", relevance_note="Same job.", source_ids=["S1"], info_completeness="minimal")
        ],
        comparison=Comparison(
            features=["Photo diagnosis"],
            rows=[ComparisonRow(competitor="LeafDoc", cells=[ComparisonCell(feature="Photo diagnosis", status=status, source_ids=ids)])],
            feature_coverage=[FeatureCoverage(feature="Photo diagnosis", competitors_with_evidence=found if counted is None else counted)],
        ),
        data_quality=DataQuality(evidence_level="limited"),
        caveats=[integrity.COMPETITOR_CAVEAT],
    )


def test_a_clean_real_competitor_result_has_no_violations() -> None:
    assert integrity.check_competitor_integrity(real_competitors(), EVIDENCE) == []


@pytest.mark.parametrize("ids", [[], ["S0"]], ids=["no source", "summary only"])
def test_an_evidence_found_cell_needs_a_real_source(ids: list[str]) -> None:
    problems = integrity.check_competitor_integrity(real_competitors(ids=ids), EVIDENCE)
    assert "comparison.rows[0].cells[0]: evidence_found needs a valid source" in problems


def test_feature_coverage_must_match_the_rows() -> None:
    problems = integrity.check_competitor_integrity(real_competitors(counted=3), EVIDENCE)
    assert problems == ["comparison.feature_coverage: does not match the comparison rows"]
    assert integrity.check_competitor_integrity(real_competitors(status="unclear", ids=[]), EVIDENCE) == []


def test_the_market_check_ignores_the_comparison_rules() -> None:
    assert integrity.check_market_integrity(clean_market(), EVIDENCE) == []
