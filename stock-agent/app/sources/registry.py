"""The source registry: what each provider can do, and how it is doing.

Capabilities are declared statically from the provider implementations —
only what the code genuinely does. Health is observed at runtime. The
two are kept separate on purpose: a source can be capable of a category
and simultaneously unhealthy, and the status API must be able to say so.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

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
    """Capabilities + configured chains + live health, in one place."""

    def __init__(
        self,
        *,
        chains: dict[Category, list[str]],
        configured: dict[str, bool] | None = None,
    ) -> None:
        self._chains = chains
        self._health: dict[str, SourceHealth] = {}
        configured = configured or {}
        for name, definition in SOURCE_DEFINITIONS.items():
            is_configured = configured.get(name, False)
            self._health[name] = SourceHealth(
                name=definition.name,
                configured=is_configured,
                status=SourceStatus.NOT_CONFIGURED if not is_configured else SourceStatus.SUCCESS,
            )

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
