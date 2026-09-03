"""The source registry: what each provider can do, and how it is doing.

Capabilities are declared statically from the provider implementations —
only what the code genuinely does. Health is observed at runtime. The
two are kept separate on purpose: a source can be capable of a category
and simultaneously unhealthy, and the status API must be able to say so.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache

from app.sources.capabilities import Capability, Category, can_serve
from app.sources.provenance import SourceStatus

SCREENER = "screener"
INDIANAPI = "indianapi"
YFINANCE = "yfinance"
FMP = "fmp"
LOCAL = "local"


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    label: str
    kind: str
    capabilities: frozenset[Capability]
    # Set when a provider is capable in principle but known-limited in
    # practice; surfaced by the status API instead of a bare "healthy".
    limitation: str | None = None


# Declared capabilities reflect the actual implementations, verified by
# reading each provider. Screener exposes a close/DMA/volume series, not
# true OHLCV, and no financial statements at all.
SOURCE_DEFINITIONS: dict[str, SourceDefinition] = {
    SCREENER: SourceDefinition(
        name=SCREENER,
        label="Screener",
        kind="historical/search",
        capabilities=frozenset({Capability.COMPANY_SEARCH, Capability.DAILY_CLOSE_SERIES}),
        limitation="Close, DMA50/200 and volume only — no open/high/low, no financial statements.",
    ),
    INDIANAPI: SourceDefinition(
        name=INDIANAPI,
        label="IndianAPI",
        kind="fundamental",
        capabilities=frozenset(
            {
                Capability.INCOME_STATEMENT,
                Capability.BALANCE_SHEET,
                Capability.CASH_FLOW,
                Capability.HISTORICAL_FINANCIALS,
                Capability.QUOTE,
            }
        ),
    ),
    YFINANCE: SourceDefinition(
        name=YFINANCE,
        label="yfinance",
        kind="market",
        capabilities=frozenset({Capability.QUOTE, Capability.OHLCV}),
    ),
    FMP: SourceDefinition(
        name=FMP,
        label="FMP",
        kind="market/fundamental",
        capabilities=frozenset(
            {
                Capability.QUOTE,
                Capability.OHLCV,
                Capability.INCOME_STATEMENT,
                Capability.BALANCE_SHEET,
                Capability.CASH_FLOW,
            }
        ),
        limitation=(
            "Returns HTTP 402 for every NSE/BSE symbol on the current plan, so it is "
            "inert as a fallback for Indian tickers; US symbols are served normally."
        ),
    ),
    LOCAL: SourceDefinition(
        name=LOCAL,
        label="Local directory",
        kind="search",
        capabilities=frozenset({Capability.COMPANY_SEARCH}),
    ),
}


@dataclass
class SourceHealth:
    """Observed runtime state. Held in memory — health is derived from
    live traffic and is intentionally not written on a request's DB
    session, which is what previously let a bookkeeping write poison the
    research transaction."""

    name: str
    status: SourceStatus = SourceStatus.NOT_CONFIGURED
    configured: bool = False
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_validated_at: datetime | None = None
    last_detail: str | None = None

    def record_success(self, *, at: datetime | None = None) -> None:
        self.last_success_at = at or datetime.now(timezone.utc)
        self.status = SourceStatus.SUCCESS
        self.last_detail = None

    def record_failure(self, status: SourceStatus, detail: str | None = None, *, at: datetime | None = None) -> None:
        self.last_error_at = at or datetime.now(timezone.utc)
        self.status = status
        self.last_detail = detail


class SourceRegistry:
    """Capabilities + configured chains + live health, in one place.

    `health_store`, when given, lets health survive across separate
    `SourceRegistry` instances (see `get_shared_health_store` below) --
    without it every construction gets its own private, empty health
    dict, which is what a caller building a fresh registry per request
    wants for `configured` (recomputed from live settings/cookie state)
    but is exactly the bug for observed health (`last_success_at` etc
    would never accumulate). Passing no store keeps the old
    every-instance-is-isolated behavior, which existing direct
    `SourceRegistry(...)` construction (e.g. in tests) still relies on.
    """

    def __init__(
        self,
        *,
        chains: dict[Category, list[str]],
        configured: dict[str, bool] | None = None,
        health_store: dict[str, SourceHealth] | None = None,
    ) -> None:
        self._chains = chains
        self._health: dict[str, SourceHealth] = health_store if health_store is not None else {}
        configured = configured or {}
        for name, definition in SOURCE_DEFINITIONS.items():
            is_configured = configured.get(name, False)
            existing = self._health.get(name)
            if existing is None:
                self._health[name] = SourceHealth(
                    name=definition.name,
                    configured=is_configured,
                    status=SourceStatus.NOT_CONFIGURED if not is_configured else SourceStatus.SUCCESS,
                )
            elif existing.configured != is_configured:
                # A real configuration change (e.g. a Screener cookie
                # was just added/removed at runtime) -- reset to the
                # same optimistic-or-unconfigured starting state a fresh
                # construction would have, rather than keeping stale
                # health from a now-irrelevant configuration.
                existing.configured = is_configured
                existing.status = SourceStatus.NOT_CONFIGURED if not is_configured else SourceStatus.SUCCESS
                existing.last_success_at = None
                existing.last_error_at = None
                existing.last_detail = None
            # else: configuration unchanged -- keep accumulated health
            # (status/timestamps) exactly as observed by live traffic.

    def definition(self, name: str) -> SourceDefinition | None:
        return SOURCE_DEFINITIONS.get(name)

    def capabilities(self, name: str) -> frozenset[Capability]:
        definition = SOURCE_DEFINITIONS.get(name)
        return definition.capabilities if definition else frozenset()

    def health(self, name: str) -> SourceHealth:
        return self._health.setdefault(name, SourceHealth(name=name))

    def all_health(self) -> list[SourceHealth]:
        return list(self._health.values())

    def chain_for(self, category: Category) -> list[str]:
        """The configured priority chain, filtered to providers that are
        both configured and actually capable of the category. A provider
        that cannot serve a category is never attempted for it."""
        return [
            name
            for name in self._chains.get(category, [])
            if self.health(name).configured and can_serve(self.capabilities(name), category)
        ]

    def declared_chain_for(self, category: Category) -> list[str]:
        """The chain as configured, before health/capability filtering —
        used by the status API to report intended roles."""
        return list(self._chains.get(category, []))

    def role_of(self, name: str, category: Category) -> str | None:
        chain = self.declared_chain_for(category)
        if name not in chain:
            return None
        return "primary" if chain[0] == name else "fallback"


@lru_cache
def get_shared_health_store() -> dict[str, SourceHealth]:
    """The process-lifetime health store `build_source_registry` passes
    to every `SourceRegistry` it builds, so a provider's observed health
    accumulates across requests instead of resetting on each one (a
    fresh registry is still built per request/call for `configured`,
    which must reflect the current cookie/settings state). `lru_cache`
    with no arguments returns the exact same dict instance every call
    within a process, exactly like `app.core.config.get_settings`.
    Tests must clear this between test functions (see
    `tests/conftest.py`) or health observed in one test leaks into the
    next."""
    return {}
