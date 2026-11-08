"""Reading market-size amounts by value, magnitude and unit (Task 1 correction to Section 7.2)."""

import pytest

from agents.figures import NO_AMOUNTS, NOT_FOUND, SUPPORTED, UNCLEAR, check_claim, check_figure, mentions_amount, read

SNIPPET = "The AI crop disease detection market was valued at USD 1.8 billion in 2025."


@pytest.mark.parametrize(
    "figure",
    [
        "USD 1.8 billion",
        "USD 1.80 billion",
        "$1.8B",
        "US$1.8bn",
        "1.8bn dollars",
        "1.8 billion USD",
        "1.8 billion (USD)",
        "1.8 billion U.S. dollars",
        "1.8-billion-dollar",
        "US$ 1,800 million",
        "USD 1800 million",
        "USD 1.8 thousand million",
        "~USD 1.8 billion (2025, global; S1)",
    ],
)
def test_the_same_amount_written_differently_is_supported(figure: str) -> None:
    assert check_figure(figure, [SNIPPET]) == SUPPORTED


@pytest.mark.parametrize(
    ("figure", "snippet"),
    [
        ("USD 1.8 million", "valued at USD 1.8 billion"),
        ("USD 1.8 billion", "valued at USD 1.8 million"),
        ("$1.8M", "valued at $1.8B"),
        ("$1.8B", "valued at $1.8M"),
        ("1.8 million farmers", "1.8 billion farmers"),
        ("INR 1.8 crore", "INR 1.8 lakh"),
        ("USD 1.8 billion", "valued at USD 1.8 trillion"),
        ("USD 1.8 billion", "valued at USD 1,800 thousand"),
    ],
    ids=["million vs billion", "billion vs million", "M vs B", "B vs M", "count magnitude", "crore vs lakh",
         "billion vs trillion", "billion vs 1.8 million written out"],
)
def test_a_different_magnitude_is_never_supported(figure: str, snippet: str) -> None:
    assert check_figure(figure, [snippet]) == NOT_FOUND


@pytest.mark.parametrize(
    ("figure", "snippet"),
    [
        ("EUR 1.8 billion", "valued at USD 1.8 billion"),
        ("$1.8 billion", "valued at A$1.8 billion"),
        ("USD 1.8 billion", "valued at 1.8 billion in 2025"),
        ("USD 1.8 billion", "1.8 billion farmers live in rural areas"),
        ("60 percent", "60 farmers joined"),
        ("1.8 percent", "valued at USD 1.8 billion"),
        ("150 million farmers", "150 million hectares of farmland"),
        ("2 million active users", "2 million users"),
    ],
    ids=["other currency", "other dollar", "currency not stated in the source", "money vs a count",
         "percent vs a count", "percent vs money", "farmers vs hectares", "qualifier not in the source"],
)
def test_a_different_unit_is_never_supported(figure: str, snippet: str) -> None:
    assert check_figure(figure, [snippet]) == NOT_FOUND


@pytest.mark.parametrize(
    ("figure", "snippet"),
    [
        ("60%", "Smartphone use among Indian farmers rose to 60 percent in 2025."),
        ("10000 farmers", "About 10,000 farmers already use photo diagnosis apps."),
        ("2 million users", "The app has 2 million active users."),
        ("150 million smallholder farmers in India", "India has 150 million smallholder farmers."),
        ("INR 500 crore", "a market of ₹5,000 million"),
        ("₹18,00,000", "about INR 1.8 million"),
        ("Rs. 5 lakh", "costs INR 500,000"),
        ("₹5 lakh crore", "worth INR 5 trillion"),
        ("USD 1,800,000", "USD 1.8 million"),
        ("EUR 2.5 billion", "worth 2.5 billion euros"),
    ],
)
def test_counts_percentages_and_indian_amounts_are_compared_by_value(figure: str, snippet: str) -> None:
    assert check_figure(figure, [snippet]) == SUPPORTED


@pytest.mark.parametrize(
    "figure",
    [
        "USD 1,8 billion",
        "USD 1.800 billion",
        "USD 1.8 bil",
        "USD 1.8 B",
        "1.8 billion",
        "1.8",
        "10 000 farmers",
        "1'800 million USD",
        "5m farmers",
        "$1.8 billion (AUD)",
        "USD 1.8 billion...",
        ".5 billion dollars",
        "₲500 million",
        "2025",
        "Not available",
        "",
    ],
    ids=["decimal comma", "dot as thousands", "unclear magnitude word", "spaced letter", "no unit", "bare number",
         "space-grouped", "apostrophe-grouped", "m without currency", "two currencies", "clipped", "leading dot",
         "unknown currency symbol", "year only", "no number", "empty"],
)
def test_a_figure_that_cannot_be_read_reliably_is_unclear_even_when_the_digits_match(figure: str) -> None:
    digits_everywhere = [SNIPPET, "1.8 1,8 18 1800 10000 500 2025", "USD 1.8 billion", "1.8 billion"]
    assert check_figure(figure, digits_everywhere) == UNCLEAR


@pytest.mark.parametrize(
    "snippet",
    [
        "valued at USD 1.8...",
        "valued at USD 1.8 bil",
        "valued at USD 1,8 billion",
        "valued at USD 1.8 M",
        "valued at USD 1 800 million",
    ],
    ids=["clipped", "unclear magnitude word", "decimal comma", "spaced letter", "space-grouped"],
)
def test_an_unclear_number_in_a_snippet_never_supports_a_figure(snippet: str) -> None:
    assert check_figure("USD 1.8 billion", [snippet]) == NOT_FOUND


def test_a_decimal_comma_is_not_read_as_a_larger_number() -> None:
    """The old guard dropped every comma, so "1,8" became 18 and supported "USD 18 billion"."""
    assert check_figure("USD 18 billion", ["valued at USD 1,8 billion"]) == NOT_FOUND
    assert read("USD 1,8 billion").amounts == ()


def test_every_amount_a_figure_states_must_appear() -> None:
    both = ["The market was USD 1.8 billion in 2025.", "It grows 12% a year."]
    assert check_figure("USD 1.8 billion, 12% CAGR", both) == SUPPORTED
    assert check_figure("USD 1.8 billion, 12% CAGR", both[:1]) == NOT_FOUND
    assert check_figure("USD 1.8-2.2 billion", ["between USD 1.8 billion and USD 2.2 billion"]) == SUPPORTED
    assert check_figure("USD 1.8-2.2 billion", ["USD 1.8 billion"]) == NOT_FOUND


def test_years_ids_and_codes_are_context_not_amounts() -> None:
    text = "In 2025-26, S1 said B2B 4G apps (FY2025) reached USD 1.8 billion by 2030."
    assert [(a.kind, a.value, a.currency) for a in read(text).amounts] == [("money", 1.8e9, "USD")]
    assert read(text).unclear == ()


def test_no_cited_text_supports_nothing() -> None:
    assert check_figure("USD 1.8 billion", []) == NOT_FOUND


# --- Task 1 scope fixes: figures inside sourced claims ----------------------------------------

CLAIMS = {
    "money in the snippet": ("Valued at $1.8B in 2025, the market keeps growing.", [SNIPPET], SUPPORTED),
    "million instead of billion": ("The market is worth USD 1.8 million.", [SNIPPET], NOT_FOUND),
    "a percentage not in the snippet": ("The market grows 12% a year.", [SNIPPET], NOT_FOUND),
    "a magnitude count with extra words": (
        "150 million smallholder farmers depend on rain.", ["India has 150 million smallholder farmers."], SUPPORTED),
    "a magnitude count of something else": ("150 million farmers", ["150 million hectares of farmland"], NOT_FOUND),
    "an unclear amount": ("The market is worth USD 1,8 billion.", [SNIPPET], UNCLEAR),
    "an amount with nothing cited": ("The market is worth USD 1.8 billion.", [], NOT_FOUND),
    "a plain count": ("About 10,000 farmers joined in 2025.", [], NO_AMOUNTS),
    "a space-grouped count": ("Around 10 000 farmers asked for help.", [], NO_AMOUNTS),
    "years and codes": ("In 2025-26 B2B 4G apps grew in 26 states.", [], NO_AMOUNTS),
    "no number": ("Most small farmers lose crops to late diagnosis.", [], NO_AMOUNTS),
}


@pytest.mark.parametrize(("claim", "cited", "expected"), CLAIMS.values(), ids=CLAIMS.keys())
def test_claims_are_checked_only_for_money_percent_and_magnitude_amounts(
    claim: str, cited: list[str], expected: str
) -> None:
    assert check_claim(claim, cited) == expected


def test_mentions_amount_finds_the_snippet_that_states_a_figure() -> None:
    assert mentions_amount("USD 1.8 billion", SNIPPET)
    assert mentions_amount("$1.8B", SNIPPET)
    assert not mentions_amount("USD 1.8 million", SNIPPET)
    assert not mentions_amount("1.8 billion", SNIPPET), "a figure without a unit matches nothing"
    assert not mentions_amount(None, SNIPPET)


def test_only_unit_bearing_unclear_numbers_are_reported_as_unclear_amounts() -> None:
    reading = read("Worth USD 1,8 billion, with 10 000 farmers.")
    assert reading.unclear_measured == ("USD 1,8 billion",)
    assert len(reading.unclear) > len(reading.unclear_measured)


# --- bug-fix phase: downloads versus users (docs/test_runs_m2/dev_market_agritech_v2.txt) --------

S9_SENTENCE = "Platforms such as Plantix have been downloaded over 10 million times."
S11_SNIPPET = (
    "Plantix has been downloaded 135 million times worldwide and is serving nearly 10 million farmers annually."
)

DOWNLOAD_COUNTS = {
    "the v2 interest signal against S9": ("Platforms like Plantix have already achieved over 10 million downloads.", [S9_SENTENCE], SUPPORTED),
    "a noun claim against a verb source": ("Plantix has 135 million downloads.", [S11_SNIPPET], SUPPORTED),
    "a verb claim against a noun source": ("Plantix was downloaded 135 million times.", ["Plantix has 135 million downloads worldwide."], SUPPORTED),
    "downloads are not the farmers served": ("Plantix has 10 million downloads.", [S11_SNIPPET], NOT_FOUND),
    "downloads are not users": ("Plantix has 10 million users.", [S9_SENTENCE.replace("over ", "")], NOT_FOUND),
    "users are not downloads": ("Plantix was downloaded 2 million times.", ["The app has 2 million active users."], NOT_FOUND),
    "installs match installs": ("The app has 5 million installs.", ["The app was installed 5 million times."], SUPPORTED),
    "installs are not downloads": ("The app has 5 million downloads.", ["The app was installed 5 million times."], NOT_FOUND),
    "a clipped unit word supports nothing": ("Plantix has over 10 million downloads.", ["Plantix has been downloaded over 10 million time..."], NOT_FOUND),
    "a clipped unit word with an ellipsis sign": ("Plantix has 10 million downloads.", ["Plantix has been downloaded 10 million time…"], NOT_FOUND),
}


@pytest.mark.parametrize(("claim", "cited", "expected"), DOWNLOAD_COUNTS.values(), ids=DOWNLOAD_COUNTS.keys())
def test_downloaded_n_times_counts_downloads_and_never_users(claim: str, cited: list[str], expected: str) -> None:
    assert check_claim(claim, cited) == expected


def test_a_count_whose_unit_word_is_clipped_is_unclear() -> None:
    reading = read("Plantix is serving nearly 10 million farm...")
    assert reading.amounts == () and reading.unclear == ("10 million",)


def test_times_without_a_download_or_install_verb_still_counts_times() -> None:
    assert [sorted(amount.words) for amount in read("The page was viewed 10 million times.").amounts] == [["time"]]
    assert check_claim("Detection is 3 times faster.", []) == NO_AMOUNTS, "plain counts are still left alone"
