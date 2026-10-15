from fastapi import APIRouter

from config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Reports whether the service is up and which keys are set (never their values)."""
    settings = get_settings()
    return {
        "status": "ok",
        "llm_configured": bool(settings.llm_api_key and settings.llm_model),
        "search_configured": bool(settings.tavily_api_key),
    }
