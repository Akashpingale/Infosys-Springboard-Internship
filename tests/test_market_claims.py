"""Claim checks added in the Task 1 bug-fix phase (agents/market_claims.py). Pure functions, no
network. The examples come from docs/test_runs_m2/dev_market_agritech_v2.txt."""

import pytest

from agents.market_claims import Claim, about_problem, added_inference, count_conflicts, problem_terms
from models.schemas import ExtractedIdea
from tests.fakes import VALID_EXTRACTION

V2_IDEA = ExtractedIdea(
    idea_title="AI-Powered Crop Disease Detection App for Small Farmers",
    problem=(
        "Small farmers often face significant delays in crop disease diagnosis while waiting for expert visits. "
        "This lack of immediate information can lead to untreated infections and crop loss."
    ),
    solution=(
        "A mobile application that provides instant disease diagnosis from a photo of a leaf. It offers "
        "treatment suggestions in the farmer's local language to ensure timely and accessible intervention."
    ),
    industry="Agriculture / AgriTech",
    target_customers=["Small farmers in India", "Farming cooperatives"],
    key_features=[
        "Photo-based disease detection",
        "Instant diagnosis",
        "Treatment suggestions",
        "Multi-language support",
        "Mobile accessibility",
    ],
)
S6 = (
    "Smallholder Farmers in Asia: Challenges and Opportunities Additionally, smallholders often face significant "
    "barriers in accessing profitable markets. The lack of direct market linkages forces them to rely on "
    "intermediaries who offer low prices and diminish their earnings."
)
S7 = "Small farmers often rely on traditional knowledge and farming practices passed down through generations."


# --- added conclusions --------------------------------------------------------------------


def test_the_v2_limitation_adds_a_may_that_its_source_does_not_state() -> None:
    claim = "Small farmers often rely on traditional knowledge, which may conflict with or reduce the perceived need for AI suggestions."
    assert added_inference(claim, [S7]) == "may"


@pytest.mark.parametrize(
    ("claim", "cited", "expected"),
    [
        ("Farmers could lose a third of the crop.", ["Farmers could lose a third of the crop to blight."], None),
        ("Adoption is likely to grow.", ["Adoption grew in 2025."], "likely"),
        ("The survey suggests farmers want faster advice.", ["Farmers want faster advice."], "suggest"),
        ("The data indicates rising demand.", ["The figures indicated rising demand."], None),
        ("Sales rose in May 2025.", ["Sales rose in 2025."], None),
        ("Most small farmers lose crops to late diagnosis.", ["Most small farmers lose crops."], None),
        ("Delays might cause losses, which implies demand.", ["Delays cause losses."], "might"),
    ],
    ids=["the source uses it too", "likely", "suggests", "indicated in the source", "the month May",
         "no hedge", "the first one added"],
)
def test_a_hedge_counts_only_when_no_cited_source_uses_it(claim: str, cited: list[str], expected: str | None) -> None:
    assert added_inference(claim, cited) == expected


# --- relevance to the idea's problem ------------------------------------------------------


def test_problem_terms_name_the_problem_not_the_customers_or_the_industry() -> None:
    terms = problem_terms(V2_IDEA)
    assert {"crop", "diseas", "diagno", "detect", "delay", "expert", "treat", "loss", "photo"} <= terms
    assert not terms & {"farmer", "small", "india", "cooper", "agritech", "agricu", "lack", "access", "often"}


def test_the_v2_cooperatives_pain_point_is_not_about_the_ideas_problem() -> None:
    claim = "Barriers in accessing profitable markets and reliance on intermediaries."
    assert not about_problem(claim, [S6], problem_terms(V2_IDEA))


def test_intervention_does_not_match_intermediaries() -> None:
    """A five-letter prefix made both 'inter', which kept the off-topic pain point."""
    assert not about_problem("Reliance on intermediaries.", [], problem_terms(V2_IDEA))


@pytest.mark.parametrize(
    ("claim", "cited"),
    [
        ("Delayed detection leading to crop loss.", []),
        ("Diagnoses arrive too late.", []),
        ("Lack of access to agronomists or laboratory facilities.", ["AI-based crop disease detection offers benefits."]),
        ("Few experts per member.", []),
        ("Treating infected plants late lowers yields.", []),
    ],
    ids=["its own words", "another form of diagnosis", "through its cited source", "expert", "treat and infect"],
)
def test_pain_points_about_the_problem_are_recognised(claim: str, cited: list[str]) -> None:
    assert about_problem(claim, cited, problem_terms(V2_IDEA))


def test_with_no_problem_terms_nothing_is_judged() -> None:
    generic = ExtractedIdea(**{**VALID_EXTRACTION, "idea_title": "Smart app", "problem": "Users often face a lack of information.",
                               "solution": "A mobile platform that provides support.", "key_features": ["App", "Platform", "Support"]})
    assert problem_terms(generic) == frozenset()
    assert about_problem("Anything at all.", [], problem_terms(generic))


# --- different counts for the same product ------------------------------------------------

V2_DEMAND = Claim(
    "The existing platform Plantix has been downloaded 135 million times worldwide and serves nearly 10 million farmers annually.",
    ("S11",),
)
V2_SIGNAL = Claim("Platforms like Plantix have already achieved over 10 million downloads.", ("S9",))


def test_the_v2_plantix_download_figures_are_reported_as_different() -> None:
    assert count_conflicts([V2_DEMAND, V2_SIGNAL]) == [
        "Sources give different figures for Plantix downloads: 135 million (S11), 10 million (S9). They may differ "
        "in date or definition, so check the sources before using either."
    ]


@pytest.mark.parametrize(
    "claims",
    [
        [V2_DEMAND],
        [V2_DEMAND, Claim("Plantix serves 10 million farmers.", ("S2",))],
        [V2_SIGNAL, Claim("Plantix has 10 million farmers using it.", ("S2",))],
        [V2_SIGNAL, Claim("Kisan apps have 135 million downloads.", ("S3",))],
        [V2_SIGNAL, Claim("Plantix has more than 10 million downloads.", ("S3",))],
        [Claim("Plantix covers 37 crops.", ("S1",)), Claim("Plantix covers 30 crops.", ("S2",))],
        [Claim("Plantix was downloaded 10 million times in 2019 and 135 million times by 2025.", ("S1",))],
    ],
    ids=["one claim", "the same farmers figure", "downloads and farmers", "another product", "the same value",
         "small counts", "a series in one claim"],
)
def test_no_conflict_is_reported_without_two_claims_counting_the_same_thing_differently(claims: list[Claim]) -> None:
    assert count_conflicts(claims) == []


def test_a_name_starting_a_sentence_is_not_taken_as_the_product() -> None:
    claims = [Claim("Platforms have 10 million downloads.", ("S1",)), Claim("Platforms have 135 million downloads.", ("S2",))]
    assert count_conflicts(claims) == []


def test_sources_with_the_same_figure_are_listed_together() -> None:
    claims = [V2_DEMAND, V2_SIGNAL, Claim("Plantix reached 135 million downloads.", ("S4",))]
    (note,) = count_conflicts(claims)
    assert "135 million (S11, S4), 10 million (S9)" in note


SNIPPET_NAMING_PLANTIX = "Apps such as Plantix help farmers diagnose crops."


def test_two_measures_of_one_product_get_separate_notes() -> None:
    claims = [
        Claim("Plantix has 135 million downloads and serves 10 million farmers.", ("S1",)),
        Claim("Plantix has 10 million downloads and serves 5 million farmers.", ("S2",)),
    ]
    notes = count_conflicts(claims, [SNIPPET_NAMING_PLANTIX])
    assert len(notes) == 2
    assert any("Plantix downloads: 135 million (S1), 10 million (S2)" in note for note in notes)
    assert any("Plantix farmers: 10 million (S1), 5 million (S2)" in note for note in notes)


def test_a_sentence_starting_name_needs_a_snippet_using_it_as_a_name() -> None:
    claims = [Claim("Plantix has 135 million downloads.", ("S1",)), Claim("Plantix has 10 million downloads.", ("S2",))]
    assert count_conflicts(claims) == [], "a capitalised first word alone may be any word"
    assert len(count_conflicts(claims, [SNIPPET_NAMING_PLANTIX])) == 1


def test_a_two_word_measure_shares_one_note() -> None:
    claims = [Claim("Plantix has 2 million active users.", ("S1",)), Claim("Plantix has 3 million active users.", ("S2",))]
    assert count_conflicts(claims, [SNIPPET_NAMING_PLANTIX]) == [
        "Sources give different figures for Plantix active and user counts: 2 million (S1), 3 million (S2). They may "
        "differ in date or definition, so check the sources before using either."
    ]
