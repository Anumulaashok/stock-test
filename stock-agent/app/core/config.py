"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    All values are sourced from environment variables (or a .env file in
    local development). Nothing here is hardcoded.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_name: str = "stock-agent"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # LLM provider selection. Only "local" is implemented for now.
    llm_provider: str = Field(default="local")

    # Local LLM (OpenAI-compatible) settings
    local_llm_base_url: str | None = Field(default=None)
    local_llm_model: str | None = Field(default=None)
    local_llm_api_key: str | None = Field(default=None)
    local_llm_connect_timeout_seconds: float = Field(default=5.0)
    # 120s default: the reference CPU-only Qwen3-8B server generates at
    # roughly 5-8 tokens/sec, so a several-hundred-token structured
    # analyst response (Step 5) can take well over the old 30s default.
    local_llm_timeout_seconds: float = Field(default=120.0)
    local_llm_enable_thinking: bool = Field(default=False)

    # External financial data provider. "fmp" (Financial Modeling Prep) is
    # the only one implemented so far.
    financial_data_provider: str = Field(default="fmp")
    financial_data_api_key: str | None = Field(default=None)
    # FMP's public API host — not a secret, but still overridable.
    financial_data_base_url: str = Field(default="https://financialmodelingprep.com/stable")
    financial_data_connect_timeout_seconds: float = Field(default=5.0)
    financial_data_timeout_seconds: float = Field(default=15.0)
    financial_data_max_retries: int = Field(default=2)
    # How many annual periods to request per statement type.
    financial_data_annual_periods_limit: int = Field(default=5)

    # External research/market-context provider (Step 8). "finnhub" is the
    # only one implemented so far. Research is optional — the app runs
    # fully without it, and a caller must explicitly opt in per request.
    research_provider: str = Field(default="finnhub")
    research_api_key: str | None = Field(default=None)
    research_base_url: str = Field(default="https://finnhub.io/api/v1")
    research_connect_timeout_seconds: float = Field(default=5.0)
    research_timeout_seconds: float = Field(default=10.0)
    research_max_retries: int = Field(default=1)
    research_default_days: int = Field(default=30)
    research_default_max_results: int = Field(default=5)
    research_stale_after_days: int = Field(default=14)

    # Database
    database_url: str | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so environment parsing happens once per process; tests can
    bypass this by constructing Settings() directly or clearing the cache.
    """
    return Settings()
