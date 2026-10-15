"""Manual LLM connection check. Prints the model name and safe error causes, never the key.

Run from the repo root:  python scripts/check_llm.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402
from utils.errors import AppError  # noqa: E402
from utils.llm_client import generate_text, list_text_models, short_model_name  # noqa: E402

MAX_LISTED = 20
TEST_PROMPT = "Reply with the word OK"


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    print(f"LLM_API_KEY set: {'yes' if settings.llm_api_key else 'no'}")
    print(f"LLM_MODEL:       {settings.llm_model or '(not set)'}")
    if not settings.llm_api_key or not settings.llm_model:
        print("Result: the AI service is not configured. Set LLM_API_KEY and LLM_MODEL in .env.")
        return 1

    print("\nModels that support text generation:")
    try:
        models = list_text_models()
    except AppError as exc:
        print(f"  Could not list models: {exc.user_message}")
        models = None
    if models is not None:
        for name in models[:MAX_LISTED]:
            print(f"  - {name}")
        if len(models) > MAX_LISTED:
            print(f"  ... and {len(models) - MAX_LISTED} more")
        configured = short_model_name(settings.llm_model)
        found = "IS" if configured in models else "is NOT"
        print(f"\nThe configured model '{configured}' {found} in the provider's list.")

    print(f'\nTest call: "{TEST_PROMPT}"')
    try:
        reply = generate_text(TEST_PROMPT).strip()
    except AppError as exc:
        print(f"Result: FAILED. {exc.user_message}")
        return 1
    print(f"Result: SUCCESS. The model replied: {reply[:50]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
