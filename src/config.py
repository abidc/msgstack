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
    def __init__(self) -> None:
        self.database_url: str = os.environ.get("DATABASE_URL", "sqlite:///msgstack.db")
        self.auth_enabled: bool = _bool("MSGSTACK_AUTH_ENABLED", False)
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.log_format: str = os.environ.get("LOG_FORMAT", "text")
        # All LLM traffic — chat and embeddings — routes through OpenRouter.
        # OPENAI_API_KEY is still read as a fallback so an existing deployment
        # keeps working if OPENROUTER_API_KEY is not set yet.
        self.openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
        self.openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.llm_base_url: str = os.environ.get(
            "LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.llm_referer: str = os.environ.get("LLM_REFERER", "https://www.msgstack.ai")
        self.llm_title: str = os.environ.get("LLM_TITLE", "MsgStack")
        self.turbovec_index_path: str = os.environ.get("TURBOVEC_INDEX_PATH", "data/msgstack_vectors.tvim")
        self.rate_limit_extract: int = _int("RATE_LIMIT_EXTRACT", 10)
        self.rate_limit_generate: int = _int("RATE_LIMIT_GENERATE", 30)
        self.rate_limit_default: int = _int("RATE_LIMIT_DEFAULT", 120)
        self.default_token_budget: int = _int("DEFAULT_TOKEN_BUDGET", 0)
        self.base_url: str = os.environ.get("MSGSTACK_BASE_URL", "http://localhost:8001")
        self.cors_origins: list[str] = os.environ.get("CORS_ORIGINS", "*").split(",")
        self.basic_auth_enabled: bool = _bool("MSGSTACK_BASIC_AUTH_ENABLED", True)
        self.basic_auth_user: str = os.environ.get("MSGSTACK_BASIC_USER", "")
        self.basic_auth_pass: str = os.environ.get("MSGSTACK_BASIC_PASS", "")
        self.pricing: dict = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 5.00, "output": 15.00},
            "text-embedding-3-small": {"input": 0.02, "output": 0.0},
            "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "openai/gpt-4o": {"input": 5.00, "output": 15.00},
            "openai/text-embedding-3-small": {"input": 0.02, "output": 0.0},
        }


settings = Settings()


#: Bare OpenAI model ids -> their OpenRouter slugs. Call sites keep using the
#: short names; routing is applied centrally in llm_model().
_OPENROUTER_SLUGS = {
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4o": "openai/gpt-4o",
    "text-embedding-3-small": "openai/text-embedding-3-small",
    "text-embedding-3-large": "openai/text-embedding-3-large",
}


def llm_model(model: str) -> str:
    """Normalise a model id for the configured provider.

    OpenRouter requires a vendor-prefixed slug; direct OpenAI rejects one. This
    keeps every call site on the short name and resolves it here.
    """
    if not _using_openrouter():
        return model.split("/", 1)[-1] if model.startswith("openai/") else model
    return _OPENROUTER_SLUGS.get(model, model)


def _using_openrouter() -> bool:
    return bool(settings.openrouter_api_key) and "openrouter" in settings.llm_base_url


def llm_client(api_key: str | None = None):
    """Return an OpenAI-SDK client pointed at the configured provider.

    Every LLM call in the codebase goes through this, so provider changes are a
    one-line config edit rather than a sweep. OpenRouter is wire-compatible with
    the OpenAI SDK for both /chat/completions and /embeddings.
    """
    from openai import OpenAI

    if _using_openrouter():
        # Ignore a caller-supplied key unless it is actually an OpenRouter key.
        # Most call sites resolve OPENAI_API_KEY themselves and pass it down;
        # sending that to OpenRouter authenticates as nobody and 401s.
        if not (api_key or "").startswith("sk-or-"):
            api_key = None
        return OpenAI(
            api_key=api_key or settings.openrouter_api_key,
            base_url=settings.llm_base_url,
            default_headers={
                "HTTP-Referer": settings.llm_referer,
                "X-Title": settings.llm_title,
            },
        )
    # Fallback: direct OpenAI, for deployments that have not set an
    # OpenRouter key yet.
    return OpenAI(api_key=api_key or settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a given token usage."""
    rates = settings.pricing.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
