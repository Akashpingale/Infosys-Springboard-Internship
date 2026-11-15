import pytest

from agents import notices
from agents import strategy_checks as checks
from agents.strategy_context import Digest, Fact, render_facts
from models.schemas import SWOT_TEXT_MAX, WHY_IT_MATTERS_MAX, StrategySourceKey, SwotRiskResult
from models.strategy_drafts import AdvisorParagraphDraft, LaunchPhaseDraft, RiskDraft, SwotItemDraft
from utils.errors import AppError

FACTS = (
    Fact("IDEA.1", "idea_problem", "Problem: Farmers lose crops while they wait for experts.", "user_provided"),
    Fact("CON.1", "constraint", "Team size: 2 people, an assumed default because the founder did not give one.", "assumption"),
    Fact("MKT.1", "market_size", "TAM for this idea's own market: USD 1.8 billion (stated by a source).", "sourced", ("market:S3",)),
    Fact("MKT.2", "demand", "Demand evidence: 60% of small farmers now own a smartphone.", "sourced", ("market:S1", "market:S3")),
    Fact("CMP.1", "competitor", "Competitor: LeafDoc (direct competitor). Photo diagnosis app.", "sourced", ("competitors:S1",)),
    Fact("CMP.2", "gap", "Possible market gap (low confidence, a hypothesis): no offline mode.", "ai_interpretation"),
)
DIGEST = Digest(facts=FACTS, text=render_facts(FACTS), max_chars=24000)
LENGTHS = {"text": SWOT_TEXT_MAX, "why_it_matters": WHY_IT_MATTERS_MAX}


def swot(text: str, basis: str = "ai_interpretation", based_on: list[str] | None = None, why: str = "It matters.") -> SwotItemDraft:
    return SwotItemDraft(text=text, why_it_matters=why, basis=basis, based_on=["MKT.2"] if based_on is None else based_on)


def risk_draft(title: str, description: str, **changes) -> RiskDraft:
    data = {
        "category": "market",
        "title": title,
        "description": description,
        "likelihood": "medium",
        "impact": "high",
        "mitigation": "Run a pilot with ten farmers.",
        "early_warning_signal": "Few repeat users.",
        "basis": "ai_interpretation",
        "based_on": ["CMP.1"],
    }
    return RiskDraft.model_validate({**data, **changes})


def full_repairs() -> checks.Repairs:
    return checks.Repairs(
        refs_removed=["MKT.99", "RSK.4"],
        to_assumption=2,
        to_interpretation=1,
        figures_removed=1,
        overclaims_removed=2,
        overclaim_phrases=["guaranteed", "risk-free"],
        duplicates_removed=1,
        cut={"strengths": 2, "risks": 1},
        shortened=3,
    )


def test_refs_are_normalised_deduplicated_and_unknown_ones_removed() -> None:
    kept, removed = checks.split_refs(["MKT.1", "mkt.2", " CMP.1 ", "[IDEA.1]", "MKT.99", "RSK.1", "MKT.1", "", "S3"], DIGEST)
    assert kept == ["MKT.1", "MKT.2", "CMP.1", "IDEA.1"]
    assert removed == ["MKT.99", "RSK.1", "S3"]


def test_an_invalid_ref_is_removed_from_the_item_with_one_warning() -> None:
    repairs = checks.Repairs()
    item = checks.check_item(swot("Demand is rising.", based_on=["MKT.2", "MKT.42", "CMP.9"]), DIGEST, repairs)
    assert item.based_on == ["MKT.2"] and item.basis == "ai_interpretation"
    assert repairs.refs_removed == ["MKT.42", "CMP.9"]
    assert repairs.warnings() == ["removed 2 links to findings that are not in the digest (MKT.42, CMP.9)"]


def test_the_cross_reference_field_can_be_named() -> None:
    repairs = checks.Repairs()
    paragraph = AdvisorParagraphDraft(text="Demand is rising.", basis="ai_interpretation", refs=["mkt.2", "MKT.77"])
    checked = checks.check_item(paragraph, DIGEST, repairs, ref_field="refs")
    assert checked.refs == ["MKT.2"] and repairs.refs_removed == ["MKT.77"]


@pytest.mark.parametrize(
    ("basis", "refs", "expected"),
    [
        ("ai_interpretation", [], "assumption"),
        ("user_provided", [], "assumption"),
        ("ai_interpretation", ["MKT.404"], "assumption"),
        ("user_provided", ["MKT.1"], "ai_interpretation"),
        ("user_provided", ["CMP.1", "CMP.2"], "ai_interpretation"),
        ("user_provided", ["CON.1"], "user_provided"),
        ("user_provided", ["MKT.1", "idea.1"], "user_provided"),
        ("ai_interpretation", ["MKT.1"], "ai_interpretation"),
        ("assumption", [], "assumption"),
        ("assumption", ["MKT.1"], "assumption"),
    ],
)
def test_basis_follows_the_valid_refs(basis: str, refs: list[str], expected: str) -> None:
    item = checks.check_item(swot("A point about farmers.", basis=basis, based_on=refs), DIGEST, checks.Repairs())
    assert item.basis == expected


def test_basis_changes_are_counted_in_one_warning_per_stage() -> None:
    repairs = checks.Repairs()
    items = [
        swot("First point.", based_on=[]),
        swot("Second point.", basis="user_provided", based_on=[]),
        swot("Third point.", basis="user_provided", based_on=["MKT.1"]),
        swot("Fourth point.", based_on=["MKT.1"]),
    ]
    for item in items:
        checks.check_item(item, DIGEST, repairs)
    assert (repairs.to_assumption, repairs.to_interpretation) == (2, 1)
    assert repairs.warnings() == [
        "basis changed: 2 points without an existing finding now marked as assumptions; 1 point attributed to "
        "the founder without an idea or constraint fact now marked as AI interpretations"
    ]


def test_sources_are_the_union_of_the_valid_refs_sources_in_order() -> None:
    assert checks.inherited_sources(["MKT.2", "MKT.1", "CMP.1", "IDEA.1", "CMP.2"], DIGEST) == [
        StrategySourceKey(analysis="market", id="S1"),
        StrategySourceKey(analysis="market", id="S3"),
        StrategySourceKey(analysis="competitors", id="S1"),
    ]
    assert checks.inherited_sources(["IDEA.1", "CON.1"], DIGEST) == []


@pytest.mark.parametrize(
    ("text", "refs"),
    [
        ("The idea's own market is about USD 1.8 billion.", ["MKT.1"]),
        ("A $1.8B market is open to a focused entrant.", ["MKT.1"]),
        ("With 60% of small farmers on smartphones, an app can reach them.", ["MKT.2"]),
        ("A team of 2 can test this with 3 villages.", []),
        ("Farmers need faster answers.", []),
    ],
)
def test_a_figure_that_a_cited_fact_states_is_kept(text: str, refs: list[str]) -> None:
    repairs = checks.Repairs()
    assert checks.check_item(swot(text, based_on=refs), DIGEST, repairs) is not None
    assert repairs.figures_removed == 0


@pytest.mark.parametrize(
    ("text", "refs", "why"),
    [
        ("The market is worth USD 5 billion.", ["MKT.1"], "It matters."),
        ("The market is worth INR 1.8 billion.", ["MKT.1"], "It matters."),
        ("60% of farmers own a smartphone.", ["MKT.1"], "It matters."),
        ("The market is worth USD 1.8 billion.", [], "It matters."),
        ("The market is worth USD 1.8 billion.", ["MKT.404"], "It matters."),
        ("Revenue could reach USD 1,8 billion soon.", ["MKT.1"], "It matters."),
        ("Farmers need faster answers.", ["MKT.2"], "It could add 25% to yields."),
        ("Ten million farmers could pay.", ["MKT.2"], "That is 10 million users."),
    ],
)
def test_an_item_stating_a_figure_no_cited_fact_contains_is_removed(text: str, refs: list[str], why: str) -> None:
    repairs = checks.Repairs()
    assert checks.check_item(swot(text, based_on=refs, why=why), DIGEST, repairs) is None
    assert repairs.figures_removed == 1
    assert repairs.refs_removed == [] and (repairs.to_assumption, repairs.to_interpretation) == (0, 0)
    assert repairs.warnings() == ["removed 1 point that stated a figure no cited finding contains"]


def test_the_figure_rule_is_available_for_a_single_text() -> None:
    assert checks.figure_supported("About USD 1.8 billion.", ["MKT.1"], DIGEST)
    assert not checks.figure_supported("About USD 2 billion.", ["MKT.1"], DIGEST)
    assert checks.figure_supported("No figure here.", [], DIGEST)


def test_the_overclaim_list_is_the_one_in_the_plan() -> None:
    assert checks.OVERCLAIM_PHRASES == ("guaranteed", "will succeed", "no competition", "risk-free", "certain to", "can't fail")


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        ("Success is GUARANTEED for early users.", "guaranteed"),
        ("The app will succeed in every district.", "will succeed"),
        ("There is no competition in this niche.", "no competition"),
        ("It is a risk free launch.", "risk-free"),
        ("It is a risk-free launch.", "risk-free"),
        ("Farmers are certain to adopt it.", "certain to"),
        ("This plan can't fail.", "can't fail"),
        ("This plan can\u2019t fail.", "can't fail"),
    ],
)
def test_an_item_that_promises_an_outcome_is_removed(text: str, phrase: str) -> None:
    repairs = checks.Repairs()
    assert checks.check_item(swot(text), DIGEST, repairs) is None
    assert repairs.overclaims_removed == 1 and repairs.overclaim_phrases == [phrase]
    assert repairs.warnings() == [f"removed 1 point that promised an outcome ({phrase})"]


@pytest.mark.parametrize(
    "text",
    [
        "Adoption is uncertain today.",
        "Competition from free apps is strong.",
        "Success will depend on trust.",
        "A risk register helps the founder.",
    ],
)
def test_cautious_wording_is_kept(text: str) -> None:
    assert checks.overclaims([text]) == []
    assert checks.check_item(swot(text), DIGEST, checks.Repairs()) is not None


def test_an_overclaim_in_any_text_field_counts() -> None:
    item = risk_draft("Slow adoption", "Farmers may wait.", mitigation="A guaranteed refund removes all doubt.")
    repairs = checks.Repairs()
    assert checks.check_item(item, DIGEST, repairs) is None and repairs.overclaim_phrases == ["guaranteed"]


def test_token_overlap_is_shared_tokens_over_the_longer_text() -> None:
    assert checks.token_overlap("alpha beta gamma delta epsilon", "alpha beta gamma delta zeta") == pytest.approx(0.8)
    assert checks.token_overlap("alpha beta gamma eta theta", "alpha beta gamma delta epsilon") == pytest.approx(0.6)
    assert checks.token_overlap("Farmers need help.", "The farmer needs help!") == 1.0
    assert checks.token_overlap("", "Farmers") == 0.0


def test_near_duplicates_keep_the_first_and_are_counted() -> None:
    repairs = checks.Repairs()
    items = [
        swot("Farmers need fast crop disease diagnosis in local languages."),
        swot("Offline mode helps rural users."),
        swot("Farmers need fast crop disease diagnosis in their local language."),
        swot("alpha beta gamma delta epsilon"),
        swot("alpha beta gamma delta zeta"),
        swot("alpha beta gamma eta theta"),
    ]
    kept = checks.remove_duplicates(items, repairs)
    assert [item.text for item in kept] == [
        "Farmers need fast crop disease diagnosis in local languages.",
        "Offline mode helps rural users.",
        "alpha beta gamma delta epsilon",
        "alpha beta gamma eta theta",
    ]
    assert repairs.duplicates_removed == 2
    assert repairs.warnings() == ["removed 2 points that repeated an earlier point"]


def test_risk_duplicates_compare_title_and_description() -> None:
    risks = [
        risk_draft("Slow adoption", "Farmers may not trust a new app."),
        risk_draft("Slow adoption", "Cooperatives may not pay for a pilot."),
        risk_draft("Slow adoption", "Farmers may not trust new apps."),
    ]
    kept = checks.remove_duplicates(risks, checks.Repairs())
    assert [item.description for item in kept] == ["Farmers may not trust a new app.", "Cooperatives may not pay for a pilot."]


def test_items_beyond_the_maximum_are_cut_from_the_end() -> None:
    repairs = checks.Repairs()
    items = [swot(f"Point {n} about farmers.") for n in range(1, 8)]
    kept = checks.cut_to_limit(items, 5, "strengths", repairs)
    assert [item.text for item in kept] == [f"Point {n} about farmers." for n in range(1, 6)]
    assert checks.cut_to_limit(kept, 5, "strengths", repairs) == kept
    assert repairs.cut == {"strengths": 2}
    assert repairs.warnings() == ["cut points beyond the list limits (strengths 2)"]


def test_long_text_is_cut_at_a_word_boundary_within_the_limit() -> None:
    text = "Small farmers need a fast and reliable way to diagnose crop disease in their own language."
    short = checks.shorten(text, 40)
    assert len(short) <= 40 and short.endswith(checks.ELLIPSIS)
    assert text.startswith(short[: -len(checks.ELLIPSIS)])
    assert text[len(short) - len(checks.ELLIPSIS)] == " "
    assert checks.shorten(text, len(text)) == text
    assert checks.shorten("x" * 50, 20) == "x" * 17 + checks.ELLIPSIS
    assert checks.shorten("abcdef", 2) == "ab"


def test_fields_over_their_limit_are_shortened_and_counted() -> None:
    repairs = checks.Repairs()
    item = swot("word " * 80, why="reason " * 40)
    shortened = checks.shorten_fields(item, LENGTHS, repairs)
    assert len(shortened.text) <= SWOT_TEXT_MAX and len(shortened.why_it_matters) <= WHY_IT_MATTERS_MAX
    assert repairs.shortened == 2
    phase = LaunchPhaseDraft(name="Launch", goal="Reach farmers.", actions=["act " * 60, "Short action."])
    fixed = checks.shorten_fields(phase, {"actions": 200}, repairs)
    assert len(fixed.actions[0]) <= 200 and fixed.actions[1] == "Short action."
    assert repairs.shortened == 3
    assert checks.shorten_fields(swot("Fine."), LENGTHS, repairs) == swot("Fine.")


def test_check_items_runs_every_check_and_reports_one_warning_per_code() -> None:
    repairs = checks.Repairs()
    items = [
        swot("Farmers want quick diagnosis.", based_on=["MKT.2", "MKT.50"]),
        swot("The market is worth USD 9 billion.", based_on=["MKT.1"]),
        swot("Success is guaranteed."),
        swot("Farmers want a quick diagnosis!"),
        swot("Cooperatives can share one account.", basis="user_provided", based_on=["CMP.2"]),
        swot("Offline mode suits villages.", based_on=[]),
        swot("Local language support builds trust " + "and more " * 40),
        swot("A sixth point about pricing."),
    ]
    kept = checks.check_items(items, DIGEST, repairs, label="strengths", maximum=4, lengths=LENGTHS)
    assert [item.text[:30] for item in kept] == [
        "Farmers want quick diagnosis.",
        "Cooperatives can share one acc",
        "Offline mode suits villages.",
        "Local language support builds ",
    ]
    assert [item.basis for item in kept] == ["ai_interpretation", "ai_interpretation", "assumption", "ai_interpretation"]
    assert all(len(item.text) <= SWOT_TEXT_MAX for item in kept)
    warnings = repairs.warnings()
    assert len(warnings) == 7
    assert warnings == [
        "removed 1 link to findings that are not in the digest (MKT.50)",
        "basis changed: 1 point without an existing finding now marked as assumptions; 1 point attributed to "
        "the founder without an idea or constraint fact now marked as AI interpretations",
        "removed 1 point that stated a figure no cited finding contains",
        "removed 1 point that promised an outcome (guaranteed)",
        "removed 1 point that repeated an earlier point",
        "cut points beyond the list limits (strengths 1)",
        "shortened 1 text over the length limit at a word boundary",
    ]


def test_no_repair_means_no_warning() -> None:
    repairs = checks.Repairs()
    kept = checks.check_items([swot("Farmers want quick diagnosis.")], DIGEST, repairs, label="strengths", maximum=5, lengths=LENGTHS)
    assert len(kept) == 1 and repairs.warnings() == []


def test_every_warning_builder_has_a_code() -> None:
    assert checks.WARNING_CODES == (
        "strategy_ref_removed",
        "strategy_basis_adjusted",
        "strategy_figure_removed",
        "strategy_overclaim_removed",
        "strategy_duplicate_removed",
        "strategy_items_cut",
        "strategy_text_shortened",
    )
    assert len(full_repairs().warnings()) == len(checks.WARNING_CODES)


@pytest.mark.parametrize("prefix", ["", "SWOT and risk: ", "strengths[0]: "])
def test_existing_notices_turn_every_strategy_warning_into_a_plain_message(prefix: str) -> None:
    for warning in full_repairs().warnings():
        notice = notices.notice_for_warning(prefix + warning)
        assert notice.code == notices.CODE_FALLBACK
        assert not notices.leaks(notice.message)
        assert "MKT" not in notice.message and "strategy_" not in notice.message
        assert notice.detail == prefix + warning


def key_shapes() -> dict[str, str]:
    return {
        "key-shaped text (Google)": "AI" + "za" + "Sy" + "A1b2C3d4" * 5,
        "key-shaped text (Gemini)": "AQ" + "." + "Ab3_" * 8,
        "key-shaped text (Tavily)": "tv" + "ly-" + "dev-" + "abc123" * 2,
        "key-shaped text (Groq)": "gs" + "k_" + "a1B2" * 7,
        "key-shaped text (secret key)": "s" + "k-" + "proj-" + "a1B2" * 6,
        "bearer token": "Bear" + "er " + "abc123def456ghi789",
        "private key block": "-----BEGIN " + "RSA PRIV" + "ATE KEY-----",
    }


@pytest.mark.parametrize("label", list(key_shapes()))
def test_key_shaped_text_is_found(label: str) -> None:
    assert checks.secret_findings(f"Start with {key_shapes()[label]} today.") == [label]


def test_a_configured_key_value_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq" + "-placeholder-" + "value")
    assert checks.secret_findings("Ask test-llm-key first.") == [checks.CONFIGURED_KEY]
    assert checks.secret_findings({"note": "then groq-placeholder-value"}) == [checks.CONFIGURED_KEY]
    monkeypatch.setenv("GROQ_API_KEY", "abc")
    assert checks.secret_findings("abc is a common word") == []


@pytest.mark.parametrize(
    "text",
    [
        "A risk-free desk-based approach for task-management teams.",
        "The bearer of bad news is the market report.",
        "Ask-me-anything sessions for farmers, see the FAQ.section.",
        "Use sk-12 as a label.",
        "Begin with a public key exchange.",
    ],
)
def test_ordinary_text_is_not_a_secret(text: str) -> None:
    assert checks.secret_findings(text) == []


def test_the_scan_walks_a_whole_result_and_fails_without_echoing_the_secret() -> None:
    secret = key_shapes()["key-shaped text (Groq)"]
    result = SwotRiskResult(limitations=["Thin data."], warnings=[f"note {secret}"])
    assert checks.secret_findings(result) == ["key-shaped text (Groq)"]
    assert checks.secret_findings({secret: "key in a map key"}) == ["key-shaped text (Groq)"]
    with pytest.raises(AppError) as raised:
        checks.ensure_no_secrets(result)
    assert secret not in str(raised.value) and secret not in raised.value.user_message
    assert checks.ensure_no_secrets(SwotRiskResult(limitations=["Thin data."])) is None
