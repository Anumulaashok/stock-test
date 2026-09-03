"""One canonical company identity, and the provider-specific symbols
derived from it.

Before this existed, every provider interpreted the user's ticker
independently and yfinance received a bare NSE ticker it cannot resolve
(`RECLTD` rather than `RECLTD.NS`), so Indian quotes failed silently.
The canonical ticker stays bare everywhere in the app; the suffix is
applied only when handing a symbol to a specific provider.
"""

from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScreenerCompanyMappingRow

NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"

# Index symbols are already provider-native and must pass through
# untouched — `^NSEI` is not a company and has no exchange suffix.
_PASSTHROUGH_PREFIXES = ("^",)


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"
    UNKNOWN = "UNKNOWN"


class CompanyIdentity(BaseModel):
    canonical_ticker: str
    company_name: str | None = None
    exchange: Exchange = Exchange.UNKNOWN
    screener_company_id: int | None = None
    screener_ticker: str | None = None
    yfinance_symbol: str | None = None
    fmp_symbol: str | None = None

    @property
    def is_index(self) -> bool:
        return self.canonical_ticker.startswith(_PASSTHROUGH_PREFIXES)


def normalize_ticker(raw: str) -> str:
    return (raw or "").strip().upper()


def _has_exchange_suffix(ticker: str) -> bool:
    return ticker.endswith((NSE_SUFFIX, BSE_SUFFIX))


def to_yfinance_symbol(ticker: str, exchange: Exchange = Exchange.NSE) -> str:
    """`RECLTD` -> `RECLTD.NS`. Symbols that already carry a suffix, and
    index symbols, are returned unchanged."""
    symbol = normalize_ticker(ticker)
    if not symbol or symbol.startswith(_PASSTHROUGH_PREFIXES) or _has_exchange_suffix(symbol):
        return symbol
    if exchange == Exchange.BSE:
        return f"{symbol}{BSE_SUFFIX}"
    if exchange == Exchange.NSE:
        return f"{symbol}{NSE_SUFFIX}"
    # Exchange genuinely unknown: don't guess a suffix that would turn a
    # resolvable US symbol into an unresolvable one.
    return symbol


def to_fmp_symbol(ticker: str, exchange: Exchange = Exchange.NSE) -> str:
    """FMP uses the same `.NS` convention for Indian listings."""
    return to_yfinance_symbol(ticker, exchange)


def strip_exchange_suffix(ticker: str) -> str:
    symbol = normalize_ticker(ticker)
    for suffix in (NSE_SUFFIX, BSE_SUFFIX):
        if symbol.endswith(suffix):
            return symbol[: -len(suffix)]
    return symbol


class CompanyIdentityResolver:
    """Resolves a user-supplied ticker to one identity, using the stored
    Screener mapping when there is one. An unknown mapping is reported as
    UNKNOWN rather than guessed."""

    def __init__(self, *, default_exchange: Exchange = Exchange.NSE) -> None:
        self._default_exchange = default_exchange

    def resolve_offline(self, ticker: str) -> CompanyIdentity:
        """Identity without a DB lookup — everything except the Screener
        company id, which is the only field that requires storage."""
        canonical = strip_exchange_suffix(ticker)
        if canonical.startswith(_PASSTHROUGH_PREFIXES):
            return CompanyIdentity(
                canonical_ticker=canonical,
                exchange=Exchange.UNKNOWN,
                yfinance_symbol=canonical,
                fmp_symbol=canonical,
            )
        exchange = self._default_exchange
        return CompanyIdentity(
            canonical_ticker=canonical,
            exchange=exchange,
            screener_ticker=canonical,
            yfinance_symbol=to_yfinance_symbol(canonical, exchange),
            fmp_symbol=to_fmp_symbol(canonical, exchange),
        )

    async def resolve(self, db: AsyncSession, ticker: str) -> CompanyIdentity:
        identity = self.resolve_offline(ticker)
        if identity.is_index:
            return identity
        row = (
            await db.execute(
                select(ScreenerCompanyMappingRow).where(
                    ScreenerCompanyMappingRow.ticker == identity.canonical_ticker
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return identity
        return identity.model_copy(
            update={
                "company_name": row.company_name,
                "screener_company_id": row.screener_company_id,
            }
        )
