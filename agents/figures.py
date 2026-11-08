"""Read amounts such as "USD 1.8 billion", "$1.8B", "₹500 crore", "60%" or "10,000 farmers".

The market-size guard (KIRO_PROMPT_M2.md Section 7.2) uses this to compare a figure with its
cited snippets by value, magnitude and unit, never by digits alone. "USD 1.8 billion", "$1.8B"
and "US$ 1,800 million" are the same amount; "USD 1.8 million", "EUR 1.8 billion", "1.8
percent" and "1.8 billion farmers" are not. Commas group thousands (1,800 or 18,00,000) and a
dot is a decimal point. A number whose value, magnitude or unit cannot be read reliably, such
as "1,8", "1.800", "10 000", "1.8 bil", "5m" or a snippet clipped right after the number or
inside the words saying what it counts ("10 million farm..."), is unclear: it never supports a
figure, and a figure that contains one is not verified. "Downloaded 10 million times" counts
downloads, so it equals "10 million downloads" but never "10 million users".
"""

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

SUPPORTED = "supported"
NOT_FOUND = "not_found"
UNCLEAR = "unclear"
NO_AMOUNTS = "no_amounts"

_SCALES = {
    1e3: ("thousand",),
    1e5: ("lakh", "lakhs", "lac", "lacs"),
    1e6: ("million", "millions", "mn", "mln", "mio"),
    1e7: ("crore", "crores", "cr"),
    1e9: ("billion", "billions", "bn", "bln", "mrd"),
    1e12: ("trillion", "trillions", "tn"),
}
SCALE_WORDS = {word: scale for scale, words in _SCALES.items() for word in words}
# Letters count only straight after the number, as in "1.8B", "10k" or "$5MM". "m" and "T"
# also mean metres and tonnes, so they count only next to a currency ("$5m", "USD 1T").
SCALE_LETTERS = {"MM": 1e6, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6, "b": 1e9, "B": 1e9, "T": 1e12}
CURRENCY_ONLY_LETTERS = frozenset({"m", "T"})
# Words after a number that may be a magnitude but have no single meaning.
UNCLEAR_WORDS = frozenset({"bil", "bill", "mil", "mill", "bio", "md", "tril", "k", "m", "b", "t"})
_UNCLEAR_NEXT = UNCLEAR_WORDS | frozenset(SCALE_WORDS)

CURRENCY_SYMBOLS = {
    "US$": "USD", "$": "USD", "A$": "AUD", "C$": "CAD", "S$": "SGD", "HK$": "HKD", "NZ$": "NZD",
    "R$": "BRL", "€": "EUR", "£": "GBP", "₹": "INR", "Rs.": "INR", "Rs": "INR", "₩": "KRW",
    "₦": "NGN", "₱": "PHP", "฿": "THB", "₫": "VND",
    "¥": "¥",  # yen or yuan, so only another ¥ matches it
}
CURRENCY_CODES = frozenset(
    "USD EUR GBP INR JPY CNY RMB AUD CAD SGD HKD NZD AED SAR CHF ZAR BRL MXN KES NGN "
    "BDT PKR LKR NPR IDR MYR PHP THB VND KRW".split()
)
CURRENCY_WORDS = {
    "dollar": "USD", "dollars": "USD", "us dollar": "USD", "us dollars": "USD",
    "u.s. dollar": "USD", "u.s. dollars": "USD", "australian dollar": "AUD", "australian dollars": "AUD",
    "canadian dollar": "CAD", "canadian dollars": "CAD", "singapore dollar": "SGD", "singapore dollars": "SGD",
    "euro": "EUR", "euros": "EUR", "rupee": "INR", "rupees": "INR", "indian rupee": "INR", "indian rupees": "INR",
}
_CODE_ALIASES = {"RMB": "CNY"}

MAX_COUNT_WORDS = 3
# "Downloaded 10 million times" counts downloads, the same as "10 million downloads". Downloads
# and installs are never users, customers or farmers.
_COUNTED_ACTION = re.compile(r"\b(download|install)(?:ed|s)?(?:[ -]+[^\W\d_]+){0,3}[ -]*$", re.IGNORECASE)
_ACTION_REACH = 60
_CLIPPED_WORD = ("..", "…")
# Words that end the description of a count: "10,000 farmers in India" counts farmers.
STOP_WORDS = frozenset(
    """a an the and or but nor of in on at by for from to with without within into onto across over
    under between among per via than as about around above below after before during since until
    who whom whose that which what where when while is are was were be been being am has have had
    do does did will would can could may might must shall should already also now still today
    currently nearly almost approximately roughly only just even each every all both either neither
    some any many most more less few several its their his her our your my this these those it they
    them we he she you i use uses used using own owns owned owning globally worldwide nationally
    nationwide annually yearly monthly daily alone overall total""".split()
)


def _either(words: Iterable[str]) -> str:
    """A regex alternation that tries longer words first."""
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


_NUMBER = r"\d(?:[\d,.]*\d)?"
_AMOUNT = re.compile(
    rf"""
    (?:(?P<symbol>{_either(CURRENCY_SYMBOLS)})\ ?|(?P<code>{_either(CURRENCY_CODES)})\ ?)?
    (?P<low>{_NUMBER})
    (?:\ ?(?:-|–|—|to)\ ?(?P<high>{_NUMBER}))?
    (?P<scale>(?:[\ -]?(?i:{_either(SCALE_WORDS)})\b\.?){{1,2}}|(?:{_either(SCALE_LETTERS)})(?![^\W\d_]))?
    (?P<percent>\ ?%|[\ -]?(?i:percent|per\ cent)\b)?
    (?P<suffix>
        [\ -]?(?i:{_either(CURRENCY_WORDS)})\b
        |\ (?:{_either(CURRENCY_CODES)})\b
        |\ ?\((?:{_either(CURRENCY_CODES)})\)
        |\ ?[$€£₹](?!\ ?\d)
    )?
    """,
    re.VERBOSE,
)
_PLAIN = re.compile(r"\d+(?:\.\d+)?")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")  # 1,800,000
_INDIAN = re.compile(r"\d{1,2}(?:,\d{2})+,\d{3}(?:\.\d+)?")  # 18,00,000
_DOT_THOUSANDS = re.compile(r"[1-9]\d{0,2}\.\d{3}")  # 1.800 is 1.8 or 1,800, by country
_SPACE_GROUPED = re.compile(r"(?<![\d.,])\d{1,3}(?: \d{3})+(?![\d.,])")  # 10 000: one number or two?
_CLIPPED = re.compile(r"\.{2,}|…")
_NEXT_WORD = re.compile(r"\+?[ -]*([^\W\d_]+)")
_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
_APOSTROPHES = "'’"
_UNIT_GROUPS = ("symbol", "code", "scale", "percent", "suffix")


@dataclass(frozen=True)
class Amount:
    value: float  # after magnitude: "USD 1.8 billion" is 1.8e9
    currency: str | None = None
    percent: bool = False
    scaled: bool = False  # written with a magnitude such as billion, crore or B
    words: frozenset[str] = frozenset()  # what a count counts, for example {"farmer"}

    @property
    def kind(self) -> str:
        return "money" if self.currency else "percent" if self.percent else "count"


@dataclass(frozen=True)
class Reading:
    amounts: tuple[Amount, ...] = ()
    unclear: tuple[str, ...] = ()  # numbers whose value, magnitude or unit is unclear
    unclear_measured: tuple[str, ...] = ()  # the unclear ones written with a currency, percent or magnitude


def _number(token: str) -> float | None:
    """The value of a number written unambiguously, or None (for example 1,8 or 1.800)."""
    if _DOT_THOUSANDS.fullmatch(token):
        return None
    if _PLAIN.fullmatch(token) or _THOUSANDS.fullmatch(token) or _INDIAN.fullmatch(token):
        return float(token.replace(",", ""))
    return None


def _is_year(token: str) -> bool:
    return len(token) == 4 and token.isdigit() and 1900 <= int(token) <= 2100


def _currencies(match: re.Match[str]) -> set[str]:
    """Every currency written before or after the number (more than one means they disagree)."""
    found = set()
    if match["symbol"]:
        found.add(CURRENCY_SYMBOLS[match["symbol"]])
    if match["code"]:
        found.add(match["code"])
    suffix = (match["suffix"] or "").strip(" -()")
    if suffix:
        found.add(CURRENCY_WORDS.get(suffix.lower()) or CURRENCY_SYMBOLS.get(suffix) or suffix)
    return {_CODE_ALIASES.get(code, code) for code in found}


def _scale(written: str) -> float:
    if written in SCALE_LETTERS:
        return SCALE_LETTERS[written]
    return math.prod(SCALE_WORDS[word.lower()] for word in re.findall(r"[^\W\d_]+", written))


def singular(word: str) -> str:
    """A simple singular form, so "farmers" and "farmer" (or "diseases") compare equal."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words_after(text: str, end: int) -> frozenset[str] | None:
    """Up to three words describing a count, ending at a stop word or punctuation. None when a
    clipped snippet cuts one of them off ("10 million farm..."), as the word could be any word."""
    words: list[str] = []
    for token in text[end : end + 80].lstrip("+ -").split(" ")[:MAX_COUNT_WORDS]:
        if token.endswith(_CLIPPED_WORD):
            return None
        word = token.rstrip(".,;:!?)").lower()
        if not _WORD.fullmatch(word) or word in STOP_WORDS:
            break
        words.append(singular(word))
        if len(word) != len(token):
            break
    return frozenset(words)


def _count_words(text: str, start: int, end: int) -> frozenset[str] | None:
    """What a count counts. "Downloaded over 10 million times" and "installed 5 million times"
    count downloads and installs, not times. None when the words are clipped."""
    words = _words_after(text, end)
    if words and "time" in words:
        action = _COUNTED_ACTION.search(text[max(start - _ACTION_REACH, 0) : start])
        if action:
            return frozenset({action.group(1).lower()})
    return words


def _beside(text: str, start: int, end: int) -> str | None:
    """What the characters around a number say about it: "skip" when it is part of a code or a
    word (S1, B2B, 4G, 5MW, COVID-19), "unclear" when its value or magnitude may be cut off or
    hidden, or None when it stands on its own."""
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    if before and (before.isalnum() or before in "_,-−–/"):
        return "skip"
    if after and (after.isalnum() or after == "_"):
        return "skip"
    if before == "." or (before and unicodedata.category(before) == "Sc"):
        return "unclear"  # ".5", or a currency symbol this module does not know
    if after and after in _APOSTROPHES and text[end + 1 : end + 2].isdigit():
        return "unclear"  # 1'800'000
    if before and before in _APOSTROPHES and text[start - 2 : start - 1].isdigit():
        return "unclear"
    if _CLIPPED.match(text, end):
        return "unclear"  # a clipped snippet may have lost the magnitude
    word = _NEXT_WORD.match(text, end)
    if word and word.group(1).lower() in _UNCLEAR_NEXT:
        return "unclear"  # "1.8 bil", "1.8 M", or a magnitude the pattern could not attach
    return None


def _parse(match: re.Match[str], text: str) -> list[Amount] | None:
    """The amounts in one match: an empty list when it is not an amount, None when unclear."""
    beside = _beside(text, *match.span())
    if beside:
        return [] if beside == "skip" else None
    values = [_number(match["low"])] + ([_number(match["high"])] if match["high"] else [])
    currencies = _currencies(match)
    scale_text = match["scale"] or ""
    percent = bool(match["percent"])
    if None in values or len(currencies) > 1 or (percent and (currencies or scale_text)):
        return None
    if scale_text in CURRENCY_ONLY_LETTERS and not currencies:
        return None  # "5m" may be metres and "5T" tonnes
    currency = next(iter(currencies), None)
    if not (currency or percent or scale_text) and _is_year(match["low"]):
        return []  # a year, or a range of years such as 2025-26, is context, not an amount
    scale = _scale(scale_text) if scale_text else 1.0
    words = frozenset() if currency or percent else _count_words(text, *match.span())
    if words is None:
        return None  # the snippet is clipped inside the words saying what is counted
    return [Amount(value * scale, currency, percent, bool(scale_text), words) for value in values]


def read(text: str | None) -> Reading:
    """Every amount in the text, plus the numbers that could not be read reliably."""
    text = " ".join((text or "").split())
    grouped = [found.span() for found in _SPACE_GROUPED.finditer(text)]
    amounts: list[Amount] = []
    unclear: list[str] = []
    measured: list[str] = []
    for match in _AMOUNT.finditer(text):
        in_group = any(start < match.end() and match.start() < end for start, end in grouped)
        parsed = None if in_group else _parse(match, text)
        if parsed is None:
            unclear.append(match.group(0))
            if any(match[group] for group in _UNIT_GROUPS):
                measured.append(match.group(0))
        else:
            amounts += parsed
    return Reading(tuple(amounts), tuple(unclear), tuple(measured))


def _stated(reading: Reading) -> list[Amount]:
    """The amounts a figure states: those with a currency, a percent or a magnitude or, when
    there are none, counts that say what they count. Years and other numbers are context."""
    measured = [amount for amount in reading.amounts if amount.currency or amount.percent or amount.scaled]
    return measured or [amount for amount in reading.amounts if amount.words]


def same_amount(figure: Amount, cited: Amount) -> bool:
    """Same kind and value; money in the same currency; a count of the same thing (every word
    describing the figure's count also describes the cited one)."""
    if figure.kind != cited.kind or not math.isclose(figure.value, cited.value, rel_tol=1e-9):
        return False
    if figure.kind == "money":
        return figure.currency == cited.currency
    if figure.kind == "count":
        return bool(figure.words) and figure.words <= cited.words
    return True


def check_figure(value: str | None, cited_texts: Iterable[str]) -> str:
    """SUPPORTED when every amount the figure states appears, with the same magnitude and unit,
    in the cited texts; UNCLEAR when the figure cannot be read reliably (an unclear number, no
    amount at all, or a magnitude with no unit such as a bare "1.8 billion"); else NOT_FOUND."""
    figure = read(value)
    wanted = _stated(figure)
    if figure.unclear or not wanted or any(amount.kind == "count" and not amount.words for amount in wanted):
        return UNCLEAR
    found = [amount for text in cited_texts for amount in read(text).amounts]
    if all(any(same_amount(amount, cited) for cited in found) for amount in wanted):
        return SUPPORTED
    return NOT_FOUND


def mentions_amount(value: str | None, text: str | None) -> bool:
    """True when the text states at least one of the figure's amounts with the same magnitude
    and unit. Used to find which cited snippet a market-size figure comes from."""
    found = read(text).amounts
    return any(same_amount(amount, cited) for amount in _stated(read(value)) for cited in found)


def _same_claim_amount(claim: Amount, cited: Amount) -> bool:
    """Like same_amount, but a count in a sentence ("150 million farmers depend on rain") only
    has to share one describing word with the cited count, because sentences add words."""
    if claim.kind != "count" or cited.kind != "count":
        return same_amount(claim, cited)
    if not math.isclose(claim.value, cited.value, rel_tol=1e-9):
        return False
    return not claim.words or not cited.words or bool(claim.words & cited.words)


def check_claim(text: str | None, cited_texts: Iterable[str]) -> str:
    """Check the figures in a sourced claim against its cited snippets.

    Only amounts written with a currency, a percent or a magnitude are checked; plain counts
    such as "10,000 farmers" and years are left alone. NO_AMOUNTS when the claim states no such
    amount; UNCLEAR when one of them cannot be read reliably; SUPPORTED when every one appears,
    with the same value and unit, in the cited texts; otherwise NOT_FOUND.
    """
    claim = read(text)
    if claim.unclear_measured:
        return UNCLEAR
    measured = [amount for amount in claim.amounts if amount.currency or amount.percent or amount.scaled]
    if not measured:
        return NO_AMOUNTS
    found = [amount for cited_text in cited_texts for amount in read(cited_text).amounts]
    if all(any(_same_claim_amount(amount, cited) for cited in found) for amount in measured):
        return SUPPORTED
    return NOT_FOUND
