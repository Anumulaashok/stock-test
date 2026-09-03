"""Where a piece of data came from.

Provenance is attached at the provider boundary and must survive
normalization, calculation, snapshot persistence, and the API response.
Losing it after normalization is the specific failure this module
prevents.
"""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FALLBACK = "FALLBACK"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    STALE = "STALE"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNREACHABLE = "UNREACHABLE"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


# Statuses that mean "this provider cannot answer right now, try the next
# one" as opposed to "this provider answered".
FALLBACK_TRIGGERING = frozenset(
    {
        SourceStatus.UNAVAILABLE,
        SourceStatus.INVALID,
        SourceStatus.AUTH_EXPIRED,
        SourceStatus.RATE_LIMITED,
        SourceStatus.NOT_CONFIGURED,
        SourceStatus.UNREACHABLE,
        SourceStatus.ERROR,
    }
)

# Auth failures are a credential problem, not a transient one; retrying
# only burns rate limit and delays the fallback.
NON_RETRYABLE = frozenset({SourceStatus.AUTH_EXPIRED, SourceStatus.NOT_CONFIGURED})


class Freshness(StrEnum):
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    DAILY = "DAILY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    CACHED = "CACHED"
    UNKNOWN = "UNKNOWN"


class Provenance(BaseModel):
    """Attached to every value the source manager returns."""

    source: str
    category: str
    status: SourceStatus
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    period: str | None = None
    freshness: Freshness = Freshness.UNKNOWN
    confidence: float = 1.0
    fallback_used: bool = False
    # Providers tried before this one, in order, with why each was skipped.
    attempts: list[str] = Field(default_factory=list)
    detail: str | None = None


class SourceAttempt(BaseModel):
    """One provider call, recorded for observability and the status API."""

    provider: str
    status: SourceStatus
    duration_ms: int | None = None
    detail: str | None = None

    def describe(self) -> str:
        return f"{self.provider}={self.status.value}"
