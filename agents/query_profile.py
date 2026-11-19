from datetime import date

from config import get_settings
from models.schemas import StrategyConstraints

SEARCH_TERMS = "Q-1"
REGION_AND_YEAR = "Q-2"
NEWS_TOPIC = "Q-3"
DIVERSE_EVIDENCE = "Q-4"
CANDIDATE_PHRASINGS = "Q-5"
MARKET_SIZE_DEPTH = "Q-6"
FLAGS = {
    "v1": frozenset(),
    "v2": frozenset(
        {SEARCH_TERMS, REGION_AND_YEAR, NEWS_TOPIC, DIVERSE_EVIDENCE, CANDIDATE_PHRASINGS, MARKET_SIZE_DEPTH}
    ),
}
NEWS_SEARCH = {"topic": "news", "time_range": "year"}
DEEP_SEARCH = "advanced"
QUERY_TERMS = 2


def uses(profile: str, flag: str) -> bool:
    return flag in FLAGS.get(profile, frozenset())


def active_profile() -> str:
    return get_settings().query_profile


def search_region(constraints: StrategyConstraints | None) -> str | None:
    if constraints is None or not FLAGS.get(active_profile()):
        return None
    return constraints.launch_region or None


def current_year() -> int:
    return date.today().year
