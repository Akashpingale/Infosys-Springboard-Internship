"""Deterministic Competitor Analysis checks (KIRO_PROMPT_M2.md Section 8.3). Pure: no LLM, no network."""

import pytest

from agents import competitor_checks as checks
from agents.integrity import COMPETITOR_CAVEAT
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
    FeatureCoverage,
    IdeaSubmission,
    LabeledItem,
    MarketGapDraft,
    QuantEstimate,
)
from tests.m2_fakes import evidence_item

EVIDENCE = [
    evidence_item("S1", "https://plantix.example/about", "Plantix offers photo diagnosis and is free to download.", "Plantix app"),
    evidence_item("S2", "https://directory.example/agrio", "Agrio alternatives: Plantix, Fasal and Map My Crop.", "Agrio alternatives"),
    evidence_item("S3", "https://plantix.example/pricing", "Plantix Pro costs INR 499 a year.", "Plantix pricing"),
]


@pytest.mark.parametrize(
    ("name", "key"),
    [("LeafDoc Pvt Ltd", "leafdoc"), ("Leaf Doc", "leafdoc"), ("Plantix App", "plantix"), ("Fasal Inc.", "fasal"),
     ("Map My Crop", "mapmycrop"), ("App", "app")],
)
def test_names_are_normalised_by_dropping_company_suffixes(name: str, key: str) -> None:
    assert checks.name_key(name) == key


@pytest.mark.parametrize(
    ("text", "name", "expected"),
    [
        ("Map My Crop specializes in precision agriculture.", "Map My Crop", True),
        ("MapMyCrop raised a seed round.", "Map My Crop", True),
        ("Plantix's app is free.", "Plantix", True),
        ("Plantix App has 10 million users.", "Plantix Pvt Ltd", True),
        ("Cropin raised funding.", "Crop", False),
        ("A plantation app.", "Plantix", False),
        ("", "Plantix", False),
        ("X is a letter.", "X", False),
    ],
)
def test_a_name_must_appear_as_whole_words(text: str, name: str, expected: bool) -> None:
    assert checks.mentions_name(text, name) is expected


def test_founder_names_come_only_from_the_free_text_fields() -> None:
    submission = IdeaSubmission(
        idea_description="A crop doctor app for farmers, better than LeafDoc for small plots.",
        industry="Agriculture / AgriTech",
        target_customers="Users of KisanBot in India",
        relevant_details="Fasal sells sensors, not diagnosis.",
    )
    text = checks.founder_text(submission)
    assert checks.mentions_name(text, "LeafDoc") and checks.mentions_name(text, "Fasal")
    assert not checks.mentions_name(text, "KisanBot"), "target customers are not where competitors are named"
    assert checks.founder_text(None) == ""


def candidate(name: str, ids: list[str], basis: str = "sourced", kind: str = "direct") -> CompetitorCandidate:
    return CompetitorCandidate(name=name, type=kind, source_ids=ids, basis=basis)


def test_candidates_are_grounded_merged_and_capped() -> None:
    names = [f"Rival{index}" for index in range(CANDIDATES_MAX + 2)]
    listing = evidence_item("S9", "https://list.example", "Rivals: " + ", ".join(names) + ".", "Rival list")
    evidence = [*EVIDENCE, listing]
    candidates = [candidate(name, ["S9"]) for name in names]
    candidates += [candidate("Plantix", ["S1"]), candidate("plantix app", ["S3"]), candidate("Ghost", ["S1"])]
    kept, warnings = checks.check_candidates(candidates, evidence, "")
    assert len(kept) == CANDIDATES_MAX
    assert sum("only 8 candidates are kept" in warning for warning in warnings) == 2 + 2, "Plantix arrives after the cap"
    assert any("'Ghost': it is not named in its cited sources" in warning for warning in warnings)


def test_duplicate_candidates_become_one_with_both_sources() -> None:
    kept, warnings = checks.check_candidates(
        [candidate("Plantix", ["S1"]), candidate("Plantix App", ["S3"])], EVIDENCE, ""
    )
    assert [(c.name, c.source_ids) for c in kept] == [("Plantix", ["S1", "S3"])] and warnings == []


@pytest.mark.parametrize(
    ("value", "snippets", "expected"),
    [
        ("INR 499 a year", ["Plantix Pro costs INR 499 a year."], True),
        ("INR 999 a year", ["Plantix Pro costs INR 499 a year."], False),
        ("USD 499 a year", ["Plantix Pro costs INR 499 a year."], False),
        ("Free", ["Plantix is free to download."], True),
        ("Freemium model", ["A freemium app with paid extras."], True),
        ("Free", ["Plantix Pro costs INR 499 a year."], False),
        ("499 per year", ["Plantix Pro costs INR 499 a year."], False),
        ("Pricing plans", ["Anything."], False),
    ],
    ids=["amount found", "other amount", "other currency", "free stated", "freemium stated", "free not stated",
         "amount without unit", "only generic words"],
)
def test_sourced_pricing_must_be_stated_in_its_cited_snippets(value: str, snippets: list[str], expected: bool) -> None:
    assert checks.pricing_supported(value, snippets) is expected


def draft(name: str = "Plantix", **fields) -> CompetitorDraft:
    base = {"name": name, "type": "direct", "relevance_note": "Same job.", "source_ids": ["S1"]}
    return CompetitorDraft(**{**base, **fields})


def test_completeness_is_counted_from_seven_facts() -> None:
    full = draft(
        offering="App", target_segment="Farmers", key_features=["Photo diagnosis"], value_proposition="Free",
        pricing_model=QuantEstimate(value="Free", status="sourced", source_ids=["S1"]), positioning="Mass market",
        strengths=[LabeledItem(text="Free", basis="sourced", source_ids=["S1"])],
    )
    assert checks.completeness(full) == "complete"
    assert checks.completeness(draft(offering="App", target_segment="Farmers", key_features=["x"])) == "partial"
    assert checks.completeness(draft(offering="App")) == "minimal"


def test_competitors_are_grounded_and_duplicates_merged() -> None:
    drafts = [
        draft("Plantix", website="https://plantix.example", key_features=["Photo diagnosis"],
              strengths=[LabeledItem(text="Free", basis="sourced", source_ids=["S1"])]),
        draft("Plantix App", source_ids=["S3"], key_features=["photo diagnosis", "Expert chat"],
              pricing_model=QuantEstimate(value="INR 499 a year", status="sourced", source_ids=["S3"]), basis="user_provided"),
        draft("Fasal", source_ids=["S2"], website="https://directory.example"),
        draft("Ghost", source_ids=["S1"]),
        draft("NoType", type=None),
        draft("NoNote", relevance_note="  "),
    ]
    competitors, names, warnings = checks.check_competitors(drafts, EVIDENCE, founder="We compete with Plantix App.")
    plantix, fasal = competitors
    assert plantix.name == "Plantix" and plantix.source_ids == ["S1", "S3"] and plantix.basis == "sourced"
    assert plantix.key_features == ["Photo diagnosis", "Expert chat"], "the same feature twice is kept once"
    assert plantix.pricing_model.status == "sourced" and plantix.website == "https://plantix.example"
    assert fasal.website is None, "a directory page is not Fasal's own website"
    assert names[checks.name_key("Plantix App")] == "Plantix"
    assert "competitors: dropped 2 with no type or relevance note" in warnings
    assert any("removed 'Ghost'; it is not named in its cited sources" in warning for warning in warnings)
    assert any(checks.WEBSITE_NOT_OWN in warning for warning in warnings)
    assert any("merged a duplicate 'Plantix App' into 'Plantix'" in warning for warning in warnings)
    assert all(isinstance(competitor, Competitor) for competitor in competitors)


def test_a_website_on_an_uncited_evidence_domain_is_removed() -> None:
    competitors, _, warnings = checks.check_competitors(
        [draft("Fasal", source_ids=["S2"], website="https://fasal.plantix.example")], EVIDENCE, ""
    )
    assert competitors[0].website is None and any(checks.WEBSITE_NOT_CITED in w for w in warnings)


def test_competitors_with_the_same_website_domain_are_merged() -> None:
    page = evidence_item(
        "S7", "https://plantixdoctor.example/about", "Plantix Doctor, also known as Plantix, diagnoses crop disease.", "About us"
    )
    drafts = [
        draft("Plantix", source_ids=["S7"], website="https://plantixdoctor.example"),
        draft("Plantix Doctor", source_ids=["S7"], website="https://www.plantixdoctor.example/"),
    ]
    competitors, _, warnings = checks.check_competitors(drafts, [*EVIDENCE, page], "")
    assert [c.name for c in competitors] == ["Plantix"]
    assert warnings == ["competitors: merged a duplicate 'Plantix Doctor' into 'Plantix'"]


def test_names_differing_only_by_spacing_are_merged() -> None:
    page = evidence_item("S7", "https://leafdoc.example", "LeafDoc (Leaf Doc) sells photo diagnosis.", "LeafDoc")
    competitors, _, warnings = checks.check_competitors(
        [draft("LeafDoc", source_ids=["S7"]), draft("Leaf Doc", source_ids=["S7"])], [*EVIDENCE, page], ""
    )
    assert [c.name for c in competitors] == ["LeafDoc"] and len(warnings) == 1


def plantix(**fields) -> Competitor:
    return Competitor(**{**dict(draft(key_features=["Expert chat"])), "info_completeness": "partial", **fields})


def test_comparison_features_start_with_the_idea_and_are_capped() -> None:
    extra = [f"Extra {index}" for index in range(10)]
    competitors = [plantix(key_features=["Expert chat", *extra])]
    features = checks.comparison_features(
        ["Photo diagnosis", "photo diagnosis", "Treatment advice"],
        ComparisonDraft(features=["Invented feature", "Expert chat", *extra]),
        competitors,
    )
    assert features[:3] == ["Photo diagnosis", "Treatment advice", "Expert chat"]
    assert len(features) == COMPARISON_FEATURES_MAX and "Invented feature" not in features


def test_cells_need_a_cited_source_naming_the_competitor_and_coverage_is_counted() -> None:
    comparison_draft = ComparisonDraft(
        features=[],
        rows=[
            ComparisonRow(
                competitor="plantix app",
                cells=[
                    ComparisonCell(feature="Photo diagnosis", status="evidence_found", source_ids=["S1"]),
                    ComparisonCell(feature="Treatment advice", status="evidence_found", source_ids=[]),
                ],
            ),
            ComparisonRow(competitor="Unknown rival", cells=[]),
        ],
    )
    comparison, warnings = checks.build_comparison(
        comparison_draft, [plantix()], {"plantix": "Plantix", "plantix app": "Plantix"},
        ["Photo diagnosis", "Treatment advice", "Local language"], EVIDENCE,
    )
    assert [row.competitor for row in comparison.rows] == ["Plantix"]
    # "Expert chat" is Plantix's own key feature, so it is compared too (Section 8.3).
    assert [cell.status for cell in comparison.rows[0].cells] == ["evidence_found", "unclear", "unclear", "unclear"]
    assert [(c.feature, c.competitors_with_evidence) for c in comparison.feature_coverage] == [
        ("Photo diagnosis", 1), ("Treatment advice", 0), ("Local language", 0), ("Expert chat", 0)
    ]
    assert warnings == [
        "comparison: 1 cell(s) marked evidence_found had no cited source naming the competitor, so they are now unclear"
    ]


def coverage_of(counts: dict[str, int]) -> Comparison:
    return Comparison(
        features=list(counts),
        rows=[],
        feature_coverage=[FeatureCoverage(feature=f, competitors_with_evidence=n) for f, n in counts.items()],
    )


def gap(related: list[str], confidence: str = "low", basis: str = "ai_interpretation") -> MarketGapDraft:
    return MarketGapDraft(description="Few rivals offer it.", related_features=related, basis=basis, confidence=confidence)


def test_gaps_are_capped_at_medium_and_always_carry_the_caveat() -> None:
    gaps, warnings = checks.check_gaps([gap(["Offline mode"], "high"), gap([])], coverage_of({"Offline mode": 0}), 4)
    assert [g.confidence for g in gaps] == ["medium", "low"]
    assert all(g.caveat == COMPETITOR_CAVEAT for g in gaps)
    assert warnings == ["market_gaps[0]: confidence lowered from high to medium; a gap is a hypothesis"]


@pytest.mark.parametrize(("covered", "kept"), [(2, True), (3, False)], ids=["half covered", "most covered"])
def test_a_gap_the_matrix_contradicts_is_removed(covered: int, kept: bool) -> None:
    gaps, warnings = checks.check_gaps([gap(["Expert chat"])], coverage_of({"Expert chat": covered}), 4)
    assert bool(gaps) is kept
    assert any("removed; the comparison shows evidence" in w for w in warnings) is not kept


def test_gap_features_not_in_the_comparison_are_removed() -> None:
    gaps, warnings = checks.check_gaps([gap(["expert chat", "Teleportation"])], coverage_of({"Expert chat": 0}), 2)
    assert gaps[0].related_features == ["Expert chat"]
    assert warnings == ["market_gaps[0]: removed related features that are not in the comparison: Teleportation"]


# --- Task 2 bug-review phase ---------------------------------------------------------------
# Each test below pins one defect found by reviewing the Task 2 implementation.

GENERIC_SNIPPET = "The AI crop disease detection market was valued at USD 1.8 billion in 2025."
DIRECTORY_SNIPPET = "Top Agrio alternatives include Plantix, Fasal and Map My Crop."


def item(item_id: str, url: str, snippet: str, title: str = "A page"):
    return evidence_item(item_id, url, snippet, title)


# C1: a name that is only an ordinary word must not be grounded by ordinary text.


@pytest.mark.parametrize(
    ("name", "text", "named"),
    [
        ("Crop App", GENERIC_SNIPPET, False),
        ("Crop App", "Crop App offers photo diagnosis.", True),
        ("AI", GENERIC_SNIPPET, False),
        ("AI", "AI is the name of the product.", False),
        ("Plantix App", DIRECTORY_SNIPPET, True),
        ("Plantix", DIRECTORY_SNIPPET, True),
        ("Map My Crop", DIRECTORY_SNIPPET, True),
        ("LeafDoc Pvt Ltd", "LeafDoc charges 5 USD a month.", True),
        ("Fasal", DIRECTORY_SNIPPET, True),
        ("Cropin", GENERIC_SNIPPET, False),
    ],
    ids=["generic word alone", "generic word in full", "two letters", "two letters named", "product suffix",
         "plain name", "three words", "corporate suffixes", "short real name", "longer word not a prefix match"],
)
def test_only_a_distinctive_name_is_matched_in_text(name: str, text: str, named: bool) -> None:
    assert checks.mentions_name(text, name) is named


def test_a_product_word_is_dropped_only_when_the_rest_can_stand_alone() -> None:
    assert checks.name_tokens("Plantix App") == ["plantix"]
    assert checks.name_tokens("Crop App") == ["crop", "app"]
    assert checks.name_tokens("LeafDoc Pvt Ltd") == ["leafdoc"]


def test_the_de_duplication_key_still_strips_the_product_word() -> None:
    """Section 8.3 asks for suffix stripping when de-duplicating, so these are one competitor."""
    assert checks.name_key("Plantix App") == checks.name_key("Plantix") == "plantix"
    assert checks.name_key("Crop App") == checks.name_key("Crop") == "crop"


def test_an_invented_competitor_named_after_an_ordinary_word_is_dropped() -> None:
    evidence = [item("S1", "https://reports.example/market", GENERIC_SNIPPET)]
    drafts = [draft("Crop App", source_ids=["S1"]), draft("AI", source_ids=["S1"])]
    competitors, _, warnings = checks.check_competitors(drafts, evidence, "")
    assert competitors == []
    assert warnings == [
        f"competitors[0]: removed 'Crop App'; {checks.NOT_NAMED}",
        f"competitors[1]: removed 'AI'; {checks.NOT_NAMED}",
    ]


def test_a_duplicate_named_with_a_product_word_still_merges() -> None:
    evidence = [item("S1", "https://plantix.example/about", "Plantix offers photo diagnosis."),
                item("S2", "https://directory.example/alternatives", DIRECTORY_SNIPPET)]
    drafts = [draft("Plantix", source_ids=["S1"]), draft("Plantix App", source_ids=["S2"], key_features=["Expert chat"])]
    competitors, names, warnings = checks.check_competitors(drafts, evidence, "")
    assert [c.name for c in competitors] == ["Plantix"]
    assert competitors[0].source_ids == ["S1", "S2"] and "Expert chat" in competitors[0].key_features
    assert names["plantixapp"] == "Plantix" if "plantixapp" in names else names["plantix"] == "Plantix"
    assert any("merged a duplicate" in warning for warning in warnings)


# C2: a page on the competitor's own domain names it, even when the snippet does not.

OWN_PAGE = [item("S1", "https://leafdoc.example/pricing",
                 "Unlimited photo diagnosis and expert chat for 5 USD a month.", "Pricing and plans")]


def test_a_page_on_the_competitors_own_domain_counts_as_naming_it() -> None:
    assert not checks.mentions_name("Pricing and plans Unlimited photo diagnosis.", "LeafDoc")
    assert checks.named_in_sources("LeafDoc", ["S1"], OWN_PAGE)


@pytest.mark.parametrize(
    ("name", "url", "owns"),
    [
        ("LeafDoc", "https://leafdoc.example/pricing", True),
        ("LeafDoc", "https://www.leafdoc.example/", True),
        ("LeafDoc App", "https://leafdoc.example/", True),
        ("Crop App", "https://cropinsight.example/", False),
        ("Crop App", "https://crop.example/", True),
        ("LeafDoc", "https://directory.example/leafdoc", False),
        ("AI", "https://ai.example/", False),
    ],
    ids=["own page", "www", "product suffix", "longer label", "exact label", "someone else's path", "too short"],
)
def test_owning_a_domain_needs_the_label_to_be_the_name(name: str, url: str, owns: bool) -> None:
    assert checks.owns_domain(name, url) is owns


def test_a_competitor_known_only_from_its_own_site_is_kept() -> None:
    competitors, _, warnings = checks.check_competitors(
        [draft("LeafDoc", website="https://leafdoc.example", source_ids=["S1"],
               pricing_model=QuantEstimate(value="5 USD a month", status="sourced", source_ids=["S1"]))],
        OWN_PAGE,
        "",
    )
    assert [c.name for c in competitors] == ["LeafDoc"]
    assert competitors[0].website == "https://leafdoc.example", "its own site is kept"
    assert competitors[0].pricing_model.status == "sourced", "the price is in the cited snippet"
    assert warnings == []


def test_a_candidate_known_only_from_its_own_site_is_kept() -> None:
    kept, warnings = checks.check_candidates(
        [CompetitorCandidate(name="LeafDoc", type="direct", source_ids=["S1"], basis="sourced")], OWN_PAGE, ""
    )
    assert [c.name for c in kept] == ["LeafDoc"] and warnings == []


# C5: a comparison cell citing the competitor's own page keeps its evidence_found status.


def test_a_cell_citing_the_competitors_own_page_keeps_evidence_found() -> None:
    comparison, warnings = checks.build_comparison(
        ComparisonDraft(
            features=[],
            rows=[ComparisonRow(competitor="LeafDoc", cells=[
                ComparisonCell(feature="Expert chat", status="evidence_found", source_ids=["S1"])
            ])],
        ),
        [plantix(name="LeafDoc", key_features=[])],
        {"leafdoc": "LeafDoc"},
        ["Expert chat"],
        OWN_PAGE,
    )
    assert [cell.status for cell in comparison.rows[0].cells] == ["evidence_found"]
    assert comparison.feature_coverage[0].competitors_with_evidence == 1
    assert warnings == []


# C4: features seen in competitor data are compared even when the model omits them.


def test_competitor_features_are_compared_even_when_the_model_omits_them() -> None:
    competitors = [plantix(name="Plantix", key_features=["Photo diagnosis", "Expert chat"]),
                   plantix(name="Fasal", key_features=["Crop monitoring"])]
    features = checks.comparison_features(["Photo diagnosis"], ComparisonDraft(features=[]), competitors)
    assert features == ["Photo diagnosis", "Expert chat", "Crop monitoring"]


def test_a_feature_the_model_invented_is_still_left_out() -> None:
    competitors = [plantix(name="Plantix", key_features=["Expert chat"])]
    draft_features = ComparisonDraft(features=["Expert chat", "Satellite imaging"])
    assert checks.comparison_features(["Photo diagnosis"], draft_features, competitors) == [
        "Photo diagnosis", "Expert chat"
    ]


def test_the_model_order_wins_over_the_remaining_competitor_features() -> None:
    competitors = [plantix(name="Plantix", key_features=["Crop monitoring", "Expert chat"])]
    draft_features = ComparisonDraft(features=["Expert chat"])
    assert checks.comparison_features([], draft_features, competitors) == ["Expert chat", "Crop monitoring"]


def test_the_feature_cap_still_applies_to_competitor_features() -> None:
    extra = [f"Feature {index}" for index in range(12)]
    competitors = [plantix(name="Plantix", key_features=extra)]
    features = checks.comparison_features(["Photo diagnosis"], ComparisonDraft(features=[]), competitors)
    assert len(features) == checks.COMPARISON_FEATURES_MAX and features[0] == "Photo diagnosis"
