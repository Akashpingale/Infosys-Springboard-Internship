"""Manual check of the Groq fallback LLM. Prints the model and a safe result, never the key.

Run from the repo root:  python scripts/check_groq.py

It makes one small real Groq call, built the way the fallback builds it (utils/groq_client.py): the
reply is held to the strict JSON schema of the competitor analysis, the largest schema the app sends,
so the check shows whether Groq accepts that schema. It needs GROQ_API_KEY in the root .env and uses
a little of the Groq quota.
"""

import logging
import sys
import time
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402
from models.schemas import CompetitorAnalysisDraft  # noqa: E402
from utils import groq_client  # noqa: E402
from utils.llm_client import MIN_DEADLINE_S, TEMPERATURE  # noqa: E402

SYSTEM_PROMPT = "You check that an API connection works. Return one JSON object only."
USER_PROMPT = (
    "Return an empty competitor analysis: no competitors, no comparison features or rows, no market "
    "gaps, no differentiation opportunities, evidence level insufficient, and no notes."
)


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    print(f"GROQ_API_KEY set: {'yes' if settings.groq_api_key else 'no'}")
    print(f"Groq model:       {groq_client.MODEL}")
    if not settings.groq_api_key:
        print("Result: the Groq fallback is off. Set GROQ_API_KEY in the root .env to switch it on.")
        return 1

    started = time.perf_counter()
    try:
        reply = groq_client.generate_json(
            SYSTEM_PROMPT,
            USER_PROMPT,
            timeout_s=max(settings.llm_timeout_s, MIN_DEADLINE_S),
            temperature=TEMPERATURE,
            reply_model=CompetitorAnalysisDraft,
        )
    except groq_client.GroqError as exc:
        code = f", code {exc.code}" if exc.code else ""
        print(f"Result: FAILED ({exc.category}, HTTP {exc.status_code}{code}).")
        return 1
    elapsed = time.perf_counter() - started

    try:
        CompetitorAnalysisDraft.model_validate_json(reply)
    except ValidationError:
        print(f"Result: FAILED. Groq answered in {elapsed:.1f}s, but not with a valid competitor analysis.")
        return 1
    print(f"Result: SUCCESS. Groq accepted the strict competitor-analysis schema and answered in {elapsed:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
