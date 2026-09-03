"""API request/response models for the historical price store
(`daily_price_history`) and forecast-accuracy evaluation
(`prediction_outcomes`) -- see `app.api.market`.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class ScreenerImportRequest(BaseModel):
    screener_company_id: int | None = Field(
        default=None,
        description="Screener.in's opaque numeric company id, e.g. 1298 for HDFCBANK. "
        "Omit to reuse a previously-registered mapping for this ticker instead.",
    )
    days: int = Field(default=365, ge=1, le=3650)
    consolidated: bool = Field(default=True)


class ScreenerImportResult(BaseModel):
    ticker: str
    rows_imported: int
    earliest_date: str | None = None
    latest_date: str | None = None
    source: str = Field(
        default="screener", description="Which provider actually supplied the imported rows."
    )
    status: str = Field(
        default="SUCCESS",
        description="SUCCESS | FALLBACK | UNAVAILABLE -- the outcome of the import as a whole.",
    )
    fallback_used: bool = False
    detail: str | None = Field(
        default=None,
        description="Why the primary source was not used, when it wasn't.",
    )


class ScreenerCompanyListImportRequest(BaseModel):
    """The raw body of one of Screener's own company-search API
    responses -- a plain list of `{id, name, url}` objects (a `null`
    id/unparseable url, e.g. Screener's own "Search everywhere: ..."
    sentinel row, is simply skipped, never an error)."""

    companies: list[dict] = Field(description="Paste Screener's company-search JSON array verbatim here.")


class ScreenerCompanyListImportResult(BaseModel):
    registered: int = Field(description="How many ticker -> Screener id mappings were stored/updated.")
    skipped: int = Field(description="Entries with a null id or unparseable url, skipped rather than guessed.")


class ScreenerMappingSummary(BaseModel):
    ticker: str
    company_name: str | None
    screener_company_id: int
    consolidated: bool


class CompanySearchResult(BaseModel):
    """One company-search suggestion. `source` is always the honest
    provenance of this particular result -- "screener" (live Screener.in
    search, auto-registered as a mapping) or "local_directory" (this
    app's bundled static NSE equity list, the same dataset
    `GET /api/v1/search` already uses) -- never blended or guessed."""

    ticker: str
    company_name: str | None
    screener_company_id: int | None
    source: str  # "screener" | "local_directory"


class CompanySearchResponse(BaseModel):
    query: str
    source: str  # "screener" | "local_directory"
    source_detail: str = Field(description="Human-readable note on why this source was used.")
    results: list[CompanySearchResult] = Field(default_factory=list)


class ScreenerCookieRequest(BaseModel):
    session_cookie: str = Field(min_length=1, description="Screener.in's 'sessionid' cookie value from a logged-in browser session.")


class ScreenerCookieStatus(BaseModel):
    """`configured` and `source` are kept for existing callers; the health
    fields are additive. The cookie value itself is never included."""

    configured: bool
    source: str | None = Field(
        default=None, description="'runtime' (set via this settings UI) or 'env' (SCREENER_SESSION_COOKIE) -- null if not configured at all."
    )
    status: str = Field(
        default="UNKNOWN",
        description=(
            "NOT_CONFIGURED | SUCCESS | AUTH_EXPIRED | RATE_LIMITED | UNREACHABLE | "
            "INVALID | UNKNOWN. UNKNOWN means the cookie has not been validated yet."
        ),
    )
    last_validated_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    detail: str | None = Field(
        default=None, description="Human-readable explanation of a non-success status."
    )


class DataSourceStatus(BaseModel):
    """One data source's declared capabilities and observed health.

    Deliberately distinguishes four things: whether a source is
    `configured`, what it is `capable_of`, which categories it is
    `primary_for`/`fallback_for`, and its live `status`.
    """

    name: str
    label: str
    type: str
    configured: bool
    status: str
    capabilities: list[str] = Field(default_factory=list)
    primary_for: list[str] = Field(default_factory=list)
    fallback_for: list[str] = Field(default_factory=list)
    last_success_at: str | None = None
    last_error_at: str | None = None
    limitation: str | None = Field(
        default=None,
        description="A known constraint on this source even when it is healthy.",
    )


class DataSourceStatusResponse(BaseModel):
    sources: list[DataSourceStatus] = Field(default_factory=list)


class IndexQuote(BaseModel):
    """One market index's current level. `status` mirrors this app's
    usual never-fabricate policy -- "unavailable" (never a guessed
    number) when the provider couldn't supply a price."""

    name: str
    symbol: str
    status: str  # "available" | "unavailable"
    current_price: Decimal | None = None
    previous_close: Decimal | None = None
    change: Decimal | None = None
    change_percent: Decimal | None = None
    source: str
    freshness: str | None = None
    warning: str | None = None


class IndexQuotesResponse(BaseModel):
    indices: list[IndexQuote]


class ForecastAccuracyEntry(BaseModel):
    horizon: str
    method: str
    prediction_date: str
    target_date: str
    predicted_price: Decimal | None
    actual_price: Decimal | None
    absolute_error: Decimal | None
    percentage_error: Decimal | None
    direction_correct: bool | None


class ForecastAccuracySummary(BaseModel):
    ticker: str
    evaluated_count: int
    newly_evaluated: int = Field(description="Rows evaluated by this call itself, before returning the full history below.")
    mean_absolute_error: Decimal | None = None
    mean_percentage_error: Decimal | None = None
    direction_accuracy: Decimal | None = Field(
        default=None, description="Fraction (0-1) of entries with a known direction that were predicted correctly."
    )
    entries: list[ForecastAccuracyEntry] = Field(default_factory=list)
