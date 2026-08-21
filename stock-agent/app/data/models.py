"""Data-ingestion domain models.

`CompanyFinancials` (from `app/models/financial_statements.py`) remains
the canonical internal representation — nothing here replaces it. These
models wrap it with provenance (`FinancialDataMetadata`) and structured,
non-throwing error reporting (`FinancialDataFetchResult`), the same
success/error-status pattern already used by `AnalystResult`.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.financial_statements import CompanyFinancials


class FinancialDataErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    COMPANY_NOT_FOUND = "company_not_found"
    INVALID_RESPONSE = "invalid_response"
    SCHEMA_MISMATCH = "schema_mismatch"
    DATA_QUALITY_ERROR = "data_quality_error"
    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    MISSING_REQUIRED_DATA = "missing_required_data"


class CompanyIdentifier(BaseModel):
    """Minimal lookup input. Only a ticker is supported for the first
    provider — other identifier types (ISIN, CIK, provider-specific ID)
    can be added without touching callers, since this is the only shape
    the rest of the app depends on."""

    ticker: str


class FinancialDataError(BaseModel):
    code: FinancialDataErrorCode
    message: str


class FinancialDataMetadata(BaseModel):
    """Provenance for one fetch — never sent to the LLM, only used for
    transparency/debugging. No credentials or raw provider payloads."""

    provider: str
    source_identifier: str
    retrieved_at: str
    currency: str | None = None
    frequency: str = "annual"
    fiscal_periods: list[str] = Field(default_factory=list)


class FinancialDataResult(BaseModel):
    company_financials: CompanyFinancials
    metadata: FinancialDataMetadata
    warnings: list[str] = Field(default_factory=list)


class FinancialDataFetchResult(BaseModel):
    """Outcome of one data-ingestion attempt: exactly one of
    `data`/`error` is set. Mirrors `AnalystResult`'s status pattern so
    callers never need exception-based control flow for expected
    failures (company not found, provider down, auth failure, ...)."""

    status: str  # "success" | "error"
    data: FinancialDataResult | None = None
    error: FinancialDataError | None = None
