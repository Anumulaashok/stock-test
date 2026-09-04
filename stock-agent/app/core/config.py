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
    # How the "don't think out loud" instruction is expressed to the
    # server's chat template, since this isn't standardized across
    # OpenAI-compatible backends:
    # - "thinking": send chat_template_kwargs.enable_thinking (vLLM/Qwen
    #   servers honor this; it's the historical default).
    # - "reasoning_effort": send chat_template_kwargs.reasoning_effort
    #   (OpenAI gpt-oss-style reasoning models, e.g. NVIDIA's hosted
    #   openai/gpt-oss-20b, ignore enable_thinking entirely and always
    #   reason at full effort unless told otherwise via this field).
    # - "none": send neither key.
    local_llm_reasoning_mode: str = Field(default="thinking")
    local_llm_reasoning_effort: str = Field(default="low")
    # Requests the server constrain decoding to valid JSON syntax
    # (OpenAI-style `response_format: {"type": "json_object"}`).
    # Off by default since not every OpenAI-compatible server recognizes
    # this field; NVIDIA's hosted API does, and without it gpt-oss-20b
    # occasionally emits free-form text that isn't valid JSON (e.g. an
    # unescaped/curly quote breaking a string) even when not truncated.
    local_llm_json_mode: bool = Field(default=False)

    # External financial data provider SELECTION only — a provider
    # identifier ("fmp", "indianapi"), never a URL. Each provider's own
    # connection details live in its own namespaced settings below (e.g.
    # FMP_*, INDIAN_API_*) so selecting one provider never requires
    # configuring another. See `app/data/factory.py` for the registry.
    financial_data_provider: str = Field(default="fmp")

    # Financial Modeling Prep (fmp)
    fmp_api_key: str | None = Field(default=None)
    # FMP's public API host — not a secret, but still overridable.
    fmp_base_url: str = Field(default="https://financialmodelingprep.com/stable")
    fmp_connect_timeout_seconds: float = Field(default=5.0)
    fmp_timeout_seconds: float = Field(default=15.0)
    fmp_max_retries: int = Field(default=2)
    # How many annual periods to request per statement type.
    fmp_annual_periods_limit: int = Field(default=5)

    # IndianAPI (indianapi) — stock.indianapi.in
    indian_api_key: str | None = Field(default=None)
    indian_api_base_url: str = Field(default="https://stock.indianapi.in")
    indian_api_connect_timeout_seconds: float = Field(default=5.0)
    indian_api_timeout_seconds: float = Field(default=15.0)
    indian_api_max_retries: int = Field(default=2)

    # Screener.in (unofficial chart API) — one-time manual historical
    # bulk-import backfill only (app.data.screener_import_service), never
    # a live MarketDataProvider/FinancialDataProvider. No key required;
    # session_cookie is optional, for whenever a Screener endpoint turns
    # out to need an authenticated session.
    screener_base_url: str = Field(default="https://www.screener.in")
    screener_session_cookie: str | None = Field(default=None)
    screener_timeout_seconds: float = Field(default=20.0)

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

    # Twice-daily auto-refresh (market open / close, IST) — recomputes
    # every ticker that has ever been successfully researched. See
    # app/scheduler/research_refresh.py. Off by default in tests via
    # this flag (never in production unless explicitly disabled) so a
    # test run never accidentally schedules a live job.
    research_auto_refresh_enabled: bool = Field(default=True)
    # Bounds how many tickers refresh concurrently -- each refresh is a
    # full research run (provider calls + up to a ~2 minute LLM call),
    # so unbounded concurrency across potentially many tickers would
    # both hammer the configured providers and spike memory/DB
    # connections at once.
    research_auto_refresh_max_concurrency: int = Field(default=2)

    # Market data provider SELECTION only — mirrors financial_data_provider's
    # policy. "fmp"/"indianapi" reuse the same connection settings above
    # (same vendor/account) but this is a fully separate abstraction
    # (`app/market/`) from FinancialDataProvider — market quotes are not
    # financial statements and must never be mixed into that domain.
    # "yfinance" needs no API key and supplies market_cap/year_high/
    # year_low/real OHLCV the other two don't for NSE/BSE tickers.
    market_data_provider: str = Field(default="fmp")
    market_data_connect_timeout_seconds: float = Field(default=5.0)
    market_data_timeout_seconds: float = Field(default=10.0)
    market_data_max_retries: int = Field(default=1)
    market_data_recent_prices_limit: int = Field(default=210)

    # Provider PRIORITY CHAINS (comma-separated, highest priority first).
    # These supersede the singular *_DATA_PROVIDER settings above, which
    # are kept as the fallback default so existing deployments that set
    # only the singular var keep the provider they already had. See
    # `app/sources/manager.py`.
    #
    # Note MARKET_DATA_PROVIDERS defaults to yfinance first: the singular
    # market_data_provider defaults to "fmp" above, but FMP returns HTTP
    # 402 for every NSE/BSE symbol, so a deploy without a .env would
    # otherwise select the one provider that cannot serve Indian tickers.
    financial_data_providers: str | None = Field(default=None)
    market_data_providers: str | None = Field(default=None)
    historical_price_providers: str = Field(default="screener,yfinance,fmp")
    company_search_providers: str = Field(default="screener,local")

    def _chain(self, configured: str | None, default: str) -> list[str]:
        raw = configured if configured is not None and configured.strip() else default
        seen: list[str] = []
        for name in raw.split(","):
            cleaned = name.strip().lower()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen

    def financial_provider_chain(self) -> list[str]:
        return self._chain(self.financial_data_providers, self.financial_data_provider)

    def market_provider_chain(self) -> list[str]:
        singular = self.market_data_provider.strip().lower()
        # "fmp" is the code default rather than a deliberate choice, and FMP
        # cannot serve NSE/BSE symbols — fall back to yfinance-first so an
        # unconfigured deploy doesn't select the one provider that can't work.
        default = "yfinance,fmp" if singular == "fmp" else singular
        return self._chain(self.market_data_providers, default)

    def historical_price_chain(self) -> list[str]:
        return self._chain(self.historical_price_providers, "screener,yfinance,fmp")

    def company_search_chain(self) -> list[str]:
        return self._chain(self.company_search_providers, "screener,local")

    # News providers (Market Opportunity sector news, Ask AI grounding).
    # Both optional — the app runs fully without either configured.
    newsdata_api_key: str | None = Field(default=None)
    newsdata_base_url: str = Field(default="https://newsdata.io/api/1")
    newsapi_api_key: str | None = Field(default=None)
    newsapi_base_url: str = Field(default="https://newsapi.org/v2")
    news_connect_timeout_seconds: float = Field(default=5.0)
    news_timeout_seconds: float = Field(default=10.0)
    news_cache_ttl_seconds: int = Field(default=1800)

    # Market Opportunity sector ranking cache. One computation evaluates
    # every constituent ticker across every sector (one real provider
    # call per ticker) -- a longer TTL than the per-ticker financial
    # data cache keeps the dashboard cheap to load repeatedly.
    sector_overview_cache_ttl_seconds: int = Field(default=1800)

    # Database — defaults to a local SQLite file so the app runs with zero
    # external setup; override with a Postgres URL in production
    # (e.g. postgresql+asyncpg://user:pass@host/db).
    database_url: str = Field(default="sqlite+aiosqlite:///./stock_agent.db")

    # Auth (Step 11). CHANGE jwt_secret_key in any non-development
    # environment — this default is intentionally insecure so the app
    # still runs out of the box for local development.
    jwt_secret_key: str = Field(default="dev-insecure-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expires_minutes: int = Field(default=60 * 24 * 7)  # 7 days

    # AI analyst response budget. 700 suits the CPU-only Qwen3-8B
    # reference server (no reasoning overhead). A reasoning model (e.g.
    # LLM_PROVIDER=nvidia's openai/gpt-oss-20b) spends part of this
    # budget on internal chain-of-thought before writing the final JSON
    # answer, so it needs a substantially larger value or every response
    # gets truncated to empty.
    analyst_max_response_tokens: int = Field(default=700)

    # Q&A assistant response budget. Answers are shorter than a full
    # analyst report (one question, one grounded answer), so this
    # defaults lower than `analyst_max_response_tokens`; a reasoning
    # model still needs more room for the same reason noted above.
    qa_max_response_tokens: int = Field(default=400)

    # API response caching (see app/cache/). Backed by the app's own SQL
    # database -- no separate cache infrastructure. Financial statements
    # don't change intra-day, so a long default TTL is safe; a market
    # quote is live data, so its default TTL is seconds, not days.
    financial_data_cache_ttl_seconds: int = Field(default=7 * 24 * 60 * 60)  # 7 days
    # A failed financial-data fetch is cached too, but briefly -- long
    # enough to collapse a burst of repeated requests for a known-bad
    # ticker, short enough that a fixed provider issue (or a fallback
    # data source recovering) is reflected again quickly.
    financial_data_negative_cache_ttl_seconds: int = Field(default=120)  # 2 minutes
    market_data_cache_ttl_seconds: int = Field(default=30)  # seconds


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so environment parsing happens once per process; tests can
    bypass this by constructing Settings() directly or clearing the cache.
    """
    return Settings()
