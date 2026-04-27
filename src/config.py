"""Centralized configuration from environment variables."""

import os


def _bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("1", "true", "yes")


def _int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


class Settings:
    # Database
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///msgstack.db")

    # Auth
    auth_enabled: bool = _bool("MSGSTACK_AUTH_ENABLED", False)

    # Admin UI — when auth is enabled, the admin UI still works via a separate
    # secret set as MSGSTACK_ADMIN_TOKEN (if unset, admin UI is open)
    admin_token: str | None = os.environ.get("MSGSTACK_ADMIN_TOKEN")

    # Logging
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format: str = os.environ.get("LOG_FORMAT", "text")  # "text" | "json"

    # OpenAI / Pinecone (re-exported for convenience)
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    pinecone_api_key: str = os.environ.get("PINECONE_API_KEY", "")
    pinecone_index: str = os.environ.get("PINECONE_INDEX", "msgstack-chunks")

    # Rate limits (requests per minute per IP/API key)
    rate_limit_extract: int = _int("RATE_LIMIT_EXTRACT", 10)
    rate_limit_generate: int = _int("RATE_LIMIT_GENERATE", 30)
    rate_limit_default: int = _int("RATE_LIMIT_DEFAULT", 120)

    # Token budget (0 = unlimited)
    default_token_budget: int = _int("DEFAULT_TOKEN_BUDGET", 0)

    # Pricing per 1M tokens (USD) — used for cost estimates
    pricing: dict = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    }

    base_url: str = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")


settings = Settings()


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a given token usage."""
    rates = settings.pricing.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
