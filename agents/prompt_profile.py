from config import DEFAULT_PROMPT_PROFILE, get_settings

SOURCE_RULES = "P-1"
FIELD_LENGTHS = "P-2"
FEATURE_WORDING = "P-4"
SPECIFIC_POINTS = "P-5"
DISTINCT_FACTS = "P-6"
MATRIX_CONSISTENCY = "M-1"
FLAGS = {
    "v1": frozenset(),
    "v2": frozenset({SOURCE_RULES, FIELD_LENGTHS, FEATURE_WORDING, SPECIFIC_POINTS, DISTINCT_FACTS, MATRIX_CONSISTENCY}),
}
RULE_TEXT = {
    SOURCE_RULES: (
        "Copy units and magnitudes exactly as the source writes them. If a number or unit is cut off in the snippet, "
        "do not use it. Do not add conclusions the source does not state. Keep pain points about this idea's problem "
        "only. If sources disagree, report both figures."
    ),
    FIELD_LENGTHS: "Keep each field to the stated length. Prefer fewer, stronger points to many weak ones.",
    FEATURE_WORDING: (
        "A competitor's key features must come from its own cited text. Use the same wording for a feature in the "
        "comparison table as in the key features list."
    ),
    SPECIFIC_POINTS: (
        "Before you finish, check that each point names something specific from this idea's own facts. Remove points "
        "that would fit any startup."
    ),
}
RULES_HEADING = "Rules for this answer:"


def uses(profile: str, flag: str) -> bool:
    return flag in FLAGS.get(profile, frozenset())


def active_profile() -> str:
    return get_settings().prompt_profile


def rules_before(profile: str, flags: tuple[str, ...]) -> list[str]:
    chosen = [RULE_TEXT[flag] for flag in flags if uses(profile, flag)]
    return [RULES_HEADING, *chosen, ""] if chosen else []


def rules_after(profile: str, flags: tuple[str, ...]) -> list[str]:
    chosen = [RULE_TEXT[flag] for flag in flags if uses(profile, flag)]
    return ["", *chosen] if chosen else []


def prompt_version(version: str, profile: str = DEFAULT_PROMPT_PROFILE) -> str:
    return version.replace("-v1", f"-{profile}", 1) if FLAGS.get(profile) else version
