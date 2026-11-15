import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from pydantic import BaseModel, ValidationError  # noqa: E402

from agents import gtm_agent, mvp_agent, swot_risk_agent  # noqa: E402
from agents.gtm_agent import (  # noqa: E402
    BOOTSTRAPPED,
    GAP_KIND,
    HIGH_COST,
    HYPOTHESIS,
    MIN_CHANNELS,
    MIN_PHASES,
    PART_END,
    PHASE_ORDER,
    SUPPORT_KINDS,
    SUPPORTED,
    channel_rank_key,
    positioning_statement,
)
from agents.mvp_agent import (  # noqa: E402
    EFFORT_MONTHS,
    FOUNDER_LISTED,
    FOUNDER_MATCH_MIN,
    MIN_FEATURES,
    REASON_ADDED,
    SCORE_PLACES,
    TIER_LATER,
    assign_tiers,
    capacity_person_months,
    feature_score,
)
from agents.strategy_checks import (  # noqa: E402
    DUPLICATE_THRESHOLD,
    adjusted_basis,
    figure_supported,
    has_unsupported_figure,
    inherited_sources,
    item_texts,
    main_text,
    overclaims,
    secret_findings,
    split_refs,
    token_overlap,
    tokens,
)
from agents.strategy_context import ASSUMPTION, Digest, build_digest, normalize_ref  # noqa: E402
from agents.swot_risk_agent import LEVEL_SCORES, MIN_RISKS, MIN_SWOT_ITEMS, QUADRANTS, severity  # noqa: E402
from models.schemas import (  # noqa: E402
    LAUNCH_PHASE_NAMES,
    RISK_CATEGORIES,
    GtmResult,
    MvpResult,
    PipelineResult,
    SwotRiskResult,
)

SECTIONS = ("swot", "mvp", "gtm")
UNLIMITED = sys.maxsize

UNREADABLE = "unreadable"
SCHEMA = "schema"
REF_UNKNOWN = "ref_unknown"
BASIS = "basis_inconsistent"
SOURCES = "sources_mismatch"
FIGURE = "figure_unsupported"
OVERCLAIM = "overclaim"
DUPLICATE = "duplicate"
SECRET = "secret"
IDS = "id_repeated"
COUNT = "count"
SHORTFALL = "shortfall_unexplained"
SEVERITY = "severity"
RISK_ORDER = "risk_order"
COVERAGE = "coverage"
SCORE = "score"
RANK = "rank"
CAPACITY = "capacity"
TIER = "tier"
DEFERRED = "deferred_reasons"
FOUNDER = "founder_feature_missing"
ORIGIN = "origin"
RISK_LINK = "risk_link"
FEATURE_LINK = "feature_link"
STATEMENT = "statement"
SEGMENT = "segment"
DIFFERENTIATOR = "differentiator_status"
CHANNEL_RANK = "channel_rank"
BUDGET = "budget_conflict"
PHASES = "launch_phases"

SHORTFALL_NOTES = {
    "swot": swot_risk_agent.FEWER_THAN_ASKED.split("{")[0],
    "mvp": mvp_agent.FEWER_THAN_ASKED.split("{")[0],
    "gtm": gtm_agent.FEWER_THAN_ASKED.split("{")[0],
}
PHASES_NOTE = gtm_agent.PHASES_MISSING.split("{")[0]

_REF_SHAPE = re.compile(r"[A-Z]+\.\d+")
_NUMBER = re.compile(r"[A-Z]+(\d+)")


@dataclass(frozen=True)
class Violation:
    rule: str
    where: str
    detail: str

    def line(self) -> str:
        return f"{self.where}: {self.rule}: {self.detail}"


def stage_digests(result: PipelineResult) -> dict[str, Digest]:
    inputs = (result.idea, result.constraints, result.market, result.competitors)
    return {
        "swot": build_digest(*inputs, max_chars=UNLIMITED),
        "mvp": build_digest(*inputs, swot=result.swot, max_chars=UNLIMITED),
        "gtm": build_digest(*inputs, swot=result.swot, mvp=result.mvp, max_chars=UNLIMITED),
    }


def _shown(refs: Sequence[str]) -> str:
    return ", ".join(normalize_ref(ref) if _REF_SHAPE.fullmatch(normalize_ref(ref)) else "a malformed ref" for ref in refs)


def _number(stored_id: str, position: int) -> int:
    found = _NUMBER.fullmatch(stored_id.strip().upper())
    return int(found.group(1)) if found else position


def _same(first: str, second: str) -> bool:
    return " ".join(first.casefold().split()) == " ".join(second.casefold().split())


def _part(text: str) -> str:
    return " ".join(str(text or "").split()).rstrip(PART_END)


def check_statement(item: BaseModel, where: str, digest: Digest, *, figure_item: BaseModel | None = None) -> list[Violation]:
    found: list[Violation] = []
    valid, unknown = split_refs(item.based_on, digest)
    if unknown:
        found.append(Violation(REF_UNKNOWN, where, f"cites {_shown(unknown)}, which is not a finding of this result"))
    expected = adjusted_basis(item.basis, valid)
    if expected != item.basis:
        found.append(Violation(BASIS, where, f"basis {item.basis} does not fit its links; expected {expected}"))
    if item.sources != inherited_sources(valid, digest):
        found.append(Violation(SOURCES, where, "the sources are not the ones inherited from the cited findings"))
    if has_unsupported_figure(item if figure_item is None else figure_item, valid, digest):
        found.append(Violation(FIGURE, where, "states a figure that no cited finding contains"))
    phrases = overclaims(item_texts(item))
    if phrases:
        found.append(Violation(OVERCLAIM, where, f"promises an outcome ({', '.join(phrases)})"))
    return found


def check_text(text: str | None, where: str, digest: Digest) -> list[Violation]:
    found: list[Violation] = []
    if not text:
        return found
    if not figure_supported(text, digest.refs, digest):
        found.append(Violation(FIGURE, where, "states a figure that no finding contains"))
    phrases = overclaims([text])
    if phrases:
        found.append(Violation(OVERCLAIM, where, f"promises an outcome ({', '.join(phrases)})"))
    return found


def check_texts(texts: Sequence[str], where: str, digest: Digest) -> list[Violation]:
    return [violation for index, text in enumerate(texts) for violation in check_text(text, f"{where}[{index}]", digest)]


def check_duplicates(items: Sequence, where: str, text_of: Callable[[BaseModel], str] = main_text) -> list[Violation]:
    return [
        Violation(DUPLICATE, f"{where}[{index}]", "repeats an earlier point")
        for index, item in enumerate(items)
        if any(token_overlap(text_of(item), text_of(earlier)) >= DUPLICATE_THRESHOLD for earlier in items[:index])
    ]


def check_ids(ids: Sequence[str], where: str) -> list[Violation]:
    repeated = sorted({value for value in ids if ids.count(value) > 1})
    return [Violation(IDS, where, f"the id {value} is used more than once") for value in repeated]


def check_shortfall(short: bool, warnings: Sequence[str], section: str, where: str) -> list[Violation]:
    if short and not any(warning.startswith(SHORTFALL_NOTES[section]) for warning in warnings):
        return [Violation(SHORTFALL, where, "fewer items than the target and no warning says so")]
    return []


def _risk_key(risk) -> tuple[int, int, int]:
    return -LEVEL_SCORES[risk.severity], -LEVEL_SCORES[risk.impact], -LEVEL_SCORES[risk.likelihood]


def check_swot(swot: SwotRiskResult, digest: Digest) -> list[Violation]:
    found: list[Violation] = []
    for name in QUADRANTS:
        items = getattr(swot, name)
        for index, item in enumerate(items):
            found += check_statement(item, f"swot.{name}[{index}] {item.id}", digest)
        found += check_duplicates(items, f"swot.{name}")
    for index, risk in enumerate(swot.risks):
        where = f"swot.risks[{index}] {risk.id}"
        found += check_statement(risk, where, digest)
        expected = severity(risk.likelihood, risk.impact)
        if risk.severity != expected:
            found.append(Violation(SEVERITY, where, f"severity {risk.severity} should be {expected}"))
    found += check_duplicates(swot.risks, "swot.risks")
    found += check_ids([item.id for name in QUADRANTS for item in getattr(swot, name)], "swot")
    found += check_ids([risk.id for risk in swot.risks], "swot.risks")
    keys = [_risk_key(risk) for risk in swot.risks]
    if keys != sorted(keys):
        found.append(Violation(RISK_ORDER, "swot.risks", "not sorted by severity, then impact, then likelihood"))
    coverage = {category: sum(1 for risk in swot.risks if risk.category == category) for category in RISK_CATEGORIES}
    if swot.risk_category_coverage != coverage:
        found.append(Violation(COVERAGE, "swot.risk_category_coverage", "does not match the risks by category"))
    if swot.coverage_gaps != [category for category, count in coverage.items() if not count]:
        found.append(Violation(COVERAGE, "swot.coverage_gaps", "does not list exactly the categories with no risk"))
    total = sum(len(getattr(swot, name)) for name in QUADRANTS)
    if total < MIN_SWOT_ITEMS or len(swot.risks) < MIN_RISKS:
        found.append(Violation(COUNT, "swot", f"{total} SWOT items and {len(swot.risks)} risks are below the minimum"))
    short = any(len(getattr(swot, name)) < swot_risk_agent.QUADRANT_RANGE[0] for name in QUADRANTS)
    short = short or len(swot.risks) < swot_risk_agent.RISKS_RANGE[0]
    found += check_shortfall(short, swot.warnings, "swot", "swot")
    found += check_text(swot.summary, "swot.summary", digest)
    found += check_texts(swot.limitations, "swot.limitations", digest)
    return found


def check_mvp(mvp: MvpResult, result: PipelineResult, digest: Digest) -> list[Violation]:
    found: list[Violation] = []
    founder = [value for value in (result.idea.key_features if result.idea else []) if value.strip()]
    risk_ids = {risk.id for risk in result.swot.risks} if result.swot else set()
    for index, feature in enumerate(mvp.features):
        where = f"mvp.features[{index}] {feature.id}"
        found += check_statement(feature, where, digest)
        expected = feature_score(feature.customer_need, feature.differentiation, feature.feasibility)
        if round(feature.score, SCORE_PLACES) != expected:
            found.append(Violation(SCORE, where, f"score {feature.score:g} should be {expected:g}"))
        if feature.origin == FOUNDER_LISTED and not any(token_overlap(feature.name, value) >= FOUNDER_MATCH_MIN for value in founder):
            found.append(Violation(ORIGIN, where, "marked founder_listed but matches no feature the founder listed"))
        unknown = [value for value in feature.mitigates_risk_ids if value not in risk_ids]
        if unknown:
            found.append(Violation(RISK_LINK, where, f"links {len(unknown)} risk id(s) that are not in the risk analysis"))
    found += check_duplicates(mvp.features, "mvp.features")
    found += check_ids([feature.id for feature in mvp.features], "mvp.features")
    numbered = [(_number(feature.id, position), feature) for position, feature in enumerate(mvp.features, 1)]
    keys = [(not feature.essential, -feature.score, EFFORT_MONTHS[feature.effort], number) for number, feature in numbered]
    if keys != sorted(keys) or [feature.rank for feature in mvp.features] != list(range(1, len(mvp.features) + 1)):
        found.append(Violation(RANK, "mvp.features", "not ranked essential first, then by score, then by lower effort"))
    used = mvp.constraints_used
    if used.team_size is None or used.months_to_mvp is None:
        found.append(Violation(CAPACITY, "mvp.constraints_used", "team size or time to first release is missing"))
    else:
        capacity = capacity_person_months(used)
        if mvp.capacity_person_months != capacity:
            found.append(Violation(CAPACITY, "mvp.capacity_person_months", f"{mvp.capacity_person_months:g} should be {capacity:g}"))
        added = {number for number, feature in numbered if mvp.deferred_reasons.get(feature.id) == REASON_ADDED}
        tiers, planned, over = assign_tiers(numbered, capacity, added)
        for index, (number, feature) in enumerate(numbered):
            if feature.tier != tiers[number]:
                found.append(Violation(TIER, f"mvp.features[{index}] {feature.id}", f"tier {feature.tier} should be {tiers[number]}"))
        if mvp.planned_person_months != round(planned, SCORE_PLACES):
            found.append(Violation(CAPACITY, "mvp.planned_person_months", f"{mvp.planned_person_months:g} should be {planned:g}"))
        if mvp.over_capacity != over:
            found.append(Violation(CAPACITY, "mvp.over_capacity", f"{mvp.over_capacity} should be {over}"))
    later = {feature.id for feature in mvp.features if feature.tier == TIER_LATER}
    if set(mvp.deferred_reasons) != later:
        found.append(Violation(DEFERRED, "mvp.deferred_reasons", "does not give one reason for each later feature"))
    for value in founder:
        if not any(token_overlap(feature.name, value) >= FOUNDER_MATCH_MIN for feature in mvp.features):
            found.append(Violation(FOUNDER, "mvp.features", "a feature the founder listed is missing"))
    if len(mvp.features) < MIN_FEATURES:
        found.append(Violation(COUNT, "mvp.features", f"{len(mvp.features)} features are below the minimum of {MIN_FEATURES}"))
    short = len(mvp.features) < mvp_agent.FEATURES_RANGE[0] or len(mvp.success_metrics) < mvp_agent.METRICS_RANGE[0]
    found += check_shortfall(short, mvp.warnings, "mvp", "mvp")
    for index, metric in enumerate(mvp.success_metrics):
        where = f"mvp.success_metrics[{index}]"
        expected = adjusted_basis(metric.basis, ())
        if expected != metric.basis:
            found.append(Violation(BASIS, where, f"basis {metric.basis} does not fit its links; expected {expected}"))
        for name in ("name", "how_to_measure", "suggested_target"):
            found += check_text(getattr(metric, name), f"{where}.{name}", digest)
    found += check_duplicates(mvp.success_metrics, "mvp.success_metrics")
    found += check_text(mvp.summary, "mvp.summary", digest)
    found += check_texts(mvp.limitations, "mvp.limitations", digest)
    return found


def _segment_choices(result: PipelineResult) -> tuple[list[str], bool, bool]:
    market = result.market
    if market is not None and market.segments:
        priority = market.priority_segment
        names = ([priority.segment_name] if priority is not None else []) + [segment.name for segment in market.segments]
        return list(dict.fromkeys(_part(name) for name in names if _part(name))), priority is not None, False
    customers = result.idea.target_customers if result.idea else []
    return list(dict.fromkeys(_part(value) for value in customers if _part(value))), False, True


def check_positioning(gtm: GtmResult, result: PipelineResult, digest: Digest) -> list[Violation]:
    positioning = gtm.positioning
    where = "gtm.positioning"
    found = check_statement(positioning, where, digest, figure_item=positioning.model_copy(update={"statement": ""}))
    if result.idea is not None and positioning.statement != positioning_statement(_part(result.idea.idea_title), positioning):
        found.append(Violation(STATEMENT, where, "the statement is not assembled from its parts"))
    choices, has_priority, founder = _segment_choices(result)
    if choices:
        allowed = choices[:1] if has_priority else choices
        if not any(_same(positioning.target_segment, name) for name in allowed):
            wanted = "the priority segment" if has_priority else "one of the founder's customers" if founder else "a market segment"
            found.append(Violation(SEGMENT, where, f"the target segment is not {wanted}"))
    if not tokens(positioning.target_segment) <= tokens(positioning.for_whom):
        found.append(Violation(SEGMENT, where, "the audience does not name the target segment"))
    if founder and positioning.basis != ASSUMPTION:
        found.append(Violation(SEGMENT, where, "built on the founder's customers but not marked as an assumption"))
    valid, _ = split_refs(positioning.based_on, digest)
    kinds = {fact.kind for fact in (digest.fact(ref) for ref in valid) if fact is not None}
    expected = HYPOTHESIS if GAP_KIND in kinds or not kinds & SUPPORT_KINDS else SUPPORTED
    if positioning.differentiator_status != expected:
        found.append(Violation(DIFFERENTIATOR, where, f"{positioning.differentiator_status} should be {expected}"))
    return found


def check_channels(gtm: GtmResult, result: PipelineResult, digest: Digest) -> list[Violation]:
    found: list[Violation] = []
    feature_ids = {feature.id for feature in result.mvp.features} if result.mvp else set()
    risk_ids = {risk.id for risk in result.swot.risks} if result.swot else set()
    bootstrapped = result.constraints is not None and result.constraints.budget_level == BOOTSTRAPPED
    for index, channel in enumerate(gtm.channels):
        where = f"gtm.channels[{index}] {channel.id}"
        found += check_statement(channel, where, digest)
        unknown = [value for value in channel.uses_feature_ids if value not in feature_ids]
        if unknown:
            found.append(Violation(FEATURE_LINK, where, f"links {len(unknown)} feature id(s) that are not in the MVP recommendation"))
        unknown = [value for value in channel.addresses_risk_ids if value not in risk_ids]
        if unknown:
            found.append(Violation(RISK_LINK, where, f"links {len(unknown)} risk id(s) that are not in the risk analysis"))
        expected = bootstrapped and channel.cost_level == HIGH_COST
        if channel.budget_conflict != expected:
            found.append(Violation(BUDGET, where, f"budget_conflict {channel.budget_conflict} should be {expected}"))
    found += check_duplicates(gtm.channels, "gtm.channels", text_of=lambda channel: channel.name)
    found += check_ids([channel.id for channel in gtm.channels], "gtm.channels")
    keys = [
        channel_rank_key(channel.audience_fit, channel.cost_level, channel.speed_to_first_result, _number(channel.id, position))
        for position, channel in enumerate(gtm.channels, 1)
    ]
    priorities = [channel.priority for channel in gtm.channels]
    first = [channel.start_here for channel in gtm.channels] != [position == 0 for position in range(len(gtm.channels))]
    if keys != sorted(keys) or priorities != list(range(1, len(gtm.channels) + 1)) or first:
        found.append(
            Violation(CHANNEL_RANK, "gtm.channels", "not ranked by audience fit, cost and speed with only the first marked start here")
        )
    if len(gtm.channels) < MIN_CHANNELS:
        found.append(Violation(COUNT, "gtm.channels", f"{len(gtm.channels)} channels are below the minimum of {MIN_CHANNELS}"))
    return found


def check_gtm(gtm: GtmResult, result: PipelineResult, digest: Digest) -> list[Violation]:
    found = check_positioning(gtm, result, digest) + check_channels(gtm, result, digest)
    for index, tactic in enumerate(gtm.early_customers):
        found += check_statement(tactic, f"gtm.early_customers[{index}]", digest)
    found += check_duplicates(gtm.early_customers, "gtm.early_customers")
    names = [phase.name for phase in gtm.launch_phases]
    if len(set(names)) != len(names) or names != sorted(names, key=PHASE_ORDER.get):
        found.append(Violation(PHASES, "gtm.launch_phases", "phases repeat or are out of order"))
    if len(gtm.launch_phases) < MIN_PHASES:
        found.append(Violation(COUNT, "gtm.launch_phases", f"{len(gtm.launch_phases)} phases are below the minimum of {MIN_PHASES}"))
    if set(names) != set(LAUNCH_PHASE_NAMES) and not any(warning.startswith(PHASES_NOTE) for warning in gtm.warnings):
        found.append(Violation(SHORTFALL, "gtm.launch_phases", "a launch phase is missing and no warning says so"))
    for index, phase in enumerate(gtm.launch_phases):
        found += check_text(phase.goal, f"gtm.launch_phases[{index}].goal", digest)
        found += check_texts(phase.actions, f"gtm.launch_phases[{index}].actions", digest)
    for index, message in enumerate(gtm.key_messages):
        for name in ("audience", "message", "proof_needed"):
            found += check_text(getattr(message, name), f"gtm.key_messages[{index}].{name}", digest)
    found += check_duplicates(gtm.key_messages, "gtm.key_messages", text_of=lambda message: message.message)
    short = len(gtm.early_customers) < gtm_agent.EARLY_CUSTOMERS_RANGE[0] or len(gtm.key_messages) < gtm_agent.KEY_MESSAGES_RANGE[0]
    short = short or any(len(phase.actions) < gtm_agent.LAUNCH_ACTIONS_RANGE[0] for phase in gtm.launch_phases)
    found += check_shortfall(short, gtm.warnings, "gtm", "gtm")
    found += check_text(gtm.summary, "gtm.summary", digest)
    found += check_texts(gtm.limitations, "gtm.limitations", digest)
    return found


def check_secrets(result: PipelineResult) -> list[Violation]:
    found: list[Violation] = []
    for name in (*SECTIONS, "constraints"):
        value = getattr(result, name)
        if value is not None:
            found += [Violation(SECRET, name, f"contains {label}") for label in secret_findings(value)]
    return found


def check_result(result: PipelineResult) -> list[Violation]:
    digests = stage_digests(result)
    found: list[Violation] = []
    if result.swot is not None:
        found += check_swot(result.swot, digests["swot"])
    if result.mvp is not None:
        found += check_mvp(result.mvp, result, digests["mvp"])
    if result.gtm is not None:
        found += check_gtm(result.gtm, result, digests["gtm"])
    return found + check_secrets(result)


def load(path: Path) -> tuple[PipelineResult | None, list[Violation]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [Violation(UNREADABLE, "file", f"could not be read as JSON ({type(exc).__name__})")]
    try:
        return PipelineResult.model_validate(data), []
    except ValidationError as exc:
        return None, [
            Violation(SCHEMA, ".".join(str(part) for part in error["loc"]) or "result", error["type"]) for error in exc.errors()
        ]


def report(path: Path) -> list[Violation]:
    result, found = load(path)
    if result is None:
        print(f"{path}: not checked; {len(found)} violation(s)")
    else:
        found = check_result(result)
        checked = [name for name in SECTIONS if getattr(result, name) is not None]
        absent = [name for name in SECTIONS if getattr(result, name) is None]
        parts = [f"checked {', '.join(checked) or 'nothing'}"]
        if absent:
            parts.append(f"not present {', '.join(absent)}")
        parts.append(f"{len(found)} violation(s)" if found else "no violations")
        print(f"{path}: {'; '.join(parts)}")
    for violation in found:
        print(f"  - {violation.line()}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check saved validation results against the Milestone 3 strategy rules. Offline: no API call is made."
    )
    parser.add_argument("files", nargs="+", type=Path, help="saved PipelineResult JSON files")
    args = parser.parse_args(argv)
    failing = sum(1 for path in args.files if report(path))
    if failing:
        print(f"{failing} of {len(args.files)} file(s) break a rule.")
        return 1
    print(f"All {len(args.files)} file(s) pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
