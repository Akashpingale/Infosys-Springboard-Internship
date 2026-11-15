import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

QUERIES = [
    ("agents/base.py", r"^class AgentContext"),
    ("agents/base.py", r"^class Agent\b"),
    ("agents/base.py", r"constraints:"),
    ("agents/base.py", r"swot:"),
    ("agents/base.py", r"mvp:"),
    ("orchestrator.py", r"^class ExtractionStage"),
    ("orchestrator.py", r"^class WebSearchStage"),
    ("orchestrator.py", r"^class AnalysisStage"),
    ("orchestrator.py", r"^STAGES:"),
    ("orchestrator.py", r"^FULL_STAGES"),
    ("orchestrator.py", r"^class StrategyStage"),
    ("orchestrator.py", r"^STRATEGY_ONLY_STAGES"),
    ("orchestrator.py", r"^STRATEGY_STAGES"),
    ("orchestrator.py", r"^class StageEvent"),
    ("orchestrator.py", r"^def _status"),
    ("orchestrator.py", r"^def _seeded"),
    ("orchestrator.py", r"^def run_pipeline"),
    ("orchestrator.py", r"^TIME_LIMIT_SHARE"),
    ("orchestrator.py", r"^def analysis_time_limit_s"),
    ("orchestrator.py", r"^STRATEGY_MAX_OUTPUT_TOKENS"),
    ("orchestrator.py", r"^SKIP_NO_ANALYSIS"),
    ("utils/deadline.py", r"^def "),
    ("utils/structured.py", r"^def "),
    ("utils/groq_client.py", r"^def strict_schema"),
    ("utils/groq_client.py", r"MAX_COMPLETION_TOKENS\s*="),
    ("utils/llm_client.py", r"^def generate_json"),
    ("utils/llm_client.py", r"output_token_limit"),
    ("utils/llm_client.py", r"^class |^def "),
    ("models/schemas.py", r"^class MarketOpportunityResult"),
    ("models/schemas.py", r"^class CompetitorAnalysisResult"),
    ("models/schemas.py", r"^class LabeledItem"),
    ("models/schemas.py", r"^Basis\b"),
    ("models/schemas.py", r"^class SourceRef"),
    ("models/schemas.py", r"^class DataQuality"),
    ("models/schemas.py", r"^class SummaryLine"),
    ("models/schemas.py", r"^class VerifyItem"),
    ("models/schemas.py", r"^class Notice"),
    ("models/schemas.py", r"^class PipelineResult"),
    ("models/schemas.py", r"^PipelineResult.model_rebuild"),
    ("agents/evidence.py", r"^def "),
    ("agents/figures.py", r"^def check_claim|^STOP_WORDS|^def singular"),
    ("agents/notices.py", r"^def build_notices|^CODE_FALLBACK|^def leaks|^STRATEGY_RULES|^STAGE_TITLES|^STRATEGY_TITLES"),
    ("agents/derived.py", r"^def "),
    ("utils/run_manager.py", r"^class RunManager|^MAX_CONCURRENT_RUNS|    def start\(|    def start_strategy|    def _work|    def _on_event|    def _finish|    def _detail_from_row|^def default_manager|^def strategy_pipeline|^def run_time_limit_s|^def strategy_time_limit_s|^TITLES"),
    ("utils/run_store.py", r"^def ensure_schema|^ADDED_COLUMNS|^CHAT_SCHEMA|^LIST_COLUMNS|    def _clean|    def delete|^REDACTED"),
    ("utils/chat_store.py", r"^class ChatStore|    def "),
    ("routes/run_routes.py", r"^def |@router"),
    ("models/api.py", r"^class RunRequest|^class StrategyRequest|^class RunStarted|^class RunDetail|^class RunSummary|^class StrategyInfo|^class ChatLimits|^class MetaResponse"),
    ("routes/meta_routes.py", r"^def "),
    ("routes/chat_routes.py", r"^class |^def |@router"),
    ("routes/strategy_routes.py", r"^def |@router"),
    ("app.py", r"include_router|chat_gate"),
    ("frontend/analysis_views.py", r"^def report_markdown|^def report_file_name|^def strategy_markdown|^def has_strategy|^def stage_label"),
    ("config.py", r"^class Settings|^def get_settings|^def _bounded_int_env|^def _bounded_float_env|strategy_time_limit_s|chat_cooldown_s"),
    ("web/src/features/results/ResultsHeader.tsx", r"TABS"),
    ("web/src/features/run/useRun.ts", r"POLL_INTERVAL_MS|ACTIVE|export function"),
    ("web/src/features/run/RunPage.tsx", r"PRINTED_TABS|hasAnyStrategy|function panel|withAsk"),
    ("web/src/lib/results.ts", r"export function collectClaims|export function claimsCiting|function strategyClaims|export function resolveStrategySources"),
    ("web/src/test/setup.ts", r"onUnhandledRequest"),
    ("web/e2e/mockApi.ts", r"throw"),
    ("tests/conftest.py", r"^def |@pytest.fixture"),
]


def main() -> None:
    selected = sys.argv[1:]
    for file, pattern in QUERIES:
        if selected and not any(name in file for name in selected):
            continue
        path = ROOT / file
        if not path.is_file():
            print(f"{file}: MISSING")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        regex = re.compile(pattern)
        hits = [(number, line) for number, line in enumerate(lines, 1) if regex.search(line)]
        print(f"== {file} /{pattern}/ ({len(lines)} lines)")
        for number, line in hits[:25]:
            print(f"  {number}: {line.strip()[:140]}")


if __name__ == "__main__":
    main()
