"""The five acceptance scenarios: a failing source must degrade the
result, never the run.

Fakes are hand-written duck types, matching the convention in
tests/test_snapshot_service.py. No live calls.
"""

from decimal import Decimal

import pytest

from app.data.models import (
    CompanyIdentifier,
    FinancialDataError,
    FinancialDataErrorCode,
    FinancialDataFetchResult,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.models.financial_statements import CompanyFinancials
from app.models.market import (
    HistoricalPricePoint,
    MarketDataError,
    MarketDataErrorCode,
    MarketQuote,
    MarketSnapshot,
    MarketSnapshotResult,
    MarketStatus,
    PriceFreshness,
)
from app.sources.capabilities import Category
from app.sources.historical import merge_by_primary
from app.sources.identity import CompanyIdentity
from app.sources.manager import DataSourceManager
from app.sources.provenance import SourceAttempt, SourceStatus
from app.sources.registry import FMP, INDIANAPI, SCREENER, YFINANCE, SourceRegistry

TICKER = "RECLTD"


# --- fakes -------------------------------------------------------------------


def _financials() -> FinancialDataFetchResult:
    return FinancialDataFetchResult(
        status="success",
        data=FinancialDataResult(
            company_financials=CompanyFinancials(company_name="REC Limited", ticker=TICKER),
            metadata=FinancialDataMetadata(
                provider="stub", source_identifier=TICKER, retrieved_at="2026-09-03T00:00:00+00:00"
            ),
        ),
    )


def _financial_error(code: FinancialDataErrorCode) -> FinancialDataFetchResult:
    return FinancialDataFetchResult(
        status="error", error=FinancialDataError(code=code, message=str(code))
    )


class FakeFinancialProvider:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.received_tickers: list[str] = []

    async def get_company_financials(self, identifier: CompanyIdentifier):
        self.received_tickers.append(identifier.ticker)
        if self._raises:
            raise self._raises
        return self._result


def _snapshot(price="421.50", prices=None) -> MarketSnapshotResult:
    quote = MarketQuote(
        ticker=TICKER,
        current_price=Decimal(price),
        previous_close=Decimal(price),
        change=Decimal(0),
        change_percent=Decimal(0),
        currency="INR",
        market_status=MarketStatus.OPEN,
        market_timestamp=None,
        data_timestamp="2026-09-03T00:00:00+00:00",
        freshness=PriceFreshness.LIVE,
        source="stub",
    )
    return MarketSnapshotResult(
        status="success",
        snapshot=MarketSnapshot(
            ticker=TICKER,
            quote=quote,
            recent_prices=prices if prices is not None else [],
            fetched_at="2026-09-03T00:00:00+00:00",
            warnings=[],
        ),
    )


def _market_error(code: MarketDataErrorCode) -> MarketSnapshotResult:
    return MarketSnapshotResult(
        status="error", error=MarketDataError(code=code, message=str(code))
    )


class FakeMarketProvider:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.received_symbols: list[str] = []

    async def get_snapshot(self, ticker: str, include_recent_prices: bool = True):
        self.received_symbols.append(ticker)
        if self._raises:
            raise self._raises
        return self._result


def _point(day: str, close: str) -> HistoricalPricePoint:
    return HistoricalPricePoint(
        timestamp=day, open=None, high=None, low=None, close=Decimal(close)
    )


class FakeHistoricalProvider:
    name = SCREENER

    def __init__(self, points=None, status=SourceStatus.SUCCESS, detail=None):
        self._points = points or []
        self._status = status
        self._detail = detail
        self.calls = 0

    async def get_recent_prices(self, db, identity: CompanyIdentity, limit: int):
        self.calls += 1
        return self._points, SourceAttempt(
            provider=self.name, status=self._status, detail=self._detail
        )


def _manager(
    *,
    financial=None,
    market=None,
    historical=None,
    configured=None,
    financial_chain=None,
    market_chain=None,
    historical_chain=None,
) -> DataSourceManager:
    registry = SourceRegistry(
        chains={
            Category.FINANCIALS: financial_chain or [INDIANAPI, FMP],
            Category.MARKET_QUOTE: market_chain or [YFINANCE, FMP],
            Category.HISTORICAL_PRICE: historical_chain or [SCREENER, YFINANCE],
        },
        configured=configured
        or {SCREENER: True, INDIANAPI: True, YFINANCE: True, FMP: True},
    )
    return DataSourceManager(
        registry=registry,
        financial_providers=financial or {},
        market_providers=market or {},
        historical_provider=historical,
        db=object() if historical else None,
        recent_prices_limit=5,
    )


# --- Scenario 1: everything healthy ------------------------------------------


async def test_healthy_path_uses_each_categorys_primary():
    indianapi = FakeFinancialProvider(_financials())
    yfinance = FakeMarketProvider(_snapshot(prices=[_point("2026-09-01", "410")]))
    screener = FakeHistoricalProvider(points=[_point("2026-09-02", "421.50")])
    manager = _manager(
        financial={INDIANAPI: indianapi}, market={YFINANCE: yfinance}, historical=screener
    )

    financials = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    snapshot = await manager.get_snapshot(TICKER)

    assert financials.status == "success"
    assert snapshot.status == "success"
    assert manager.resolved_source(Category.FINANCIALS) == INDIANAPI
    assert manager.resolved_source(Category.MARKET_QUOTE) == YFINANCE
    assert manager.resolved_source(Category.HISTORICAL_PRICE) == SCREENER
    assert not manager.used_fallback(Category.FINANCIALS)
    # Screener's series replaced the market provider's.
    assert [p.timestamp for p in snapshot.snapshot.recent_prices] == ["2026-09-02"]


async def test_market_provider_receives_the_suffixed_symbol_not_the_canonical_one():
    yfinance = FakeMarketProvider(_snapshot())
    manager = _manager(market={YFINANCE: yfinance})
    await manager.get_snapshot(TICKER, include_recent_prices=False)
    assert yfinance.received_symbols == ["RECLTD.NS"]


async def test_financial_provider_receives_the_bare_canonical_ticker():
    indianapi = FakeFinancialProvider(_financials())
    manager = _manager(financial={INDIANAPI: indianapi})
    await manager.get_company_financials(CompanyIdentifier(ticker="recltd.ns"))
    assert indianapi.received_tickers == ["RECLTD"]


# --- Scenario 2: Screener cookie expired -------------------------------------


async def test_expired_screener_cookie_falls_back_and_research_continues():
    """The scenario that matters most: an expired cookie must degrade
    historical prices to the market provider, not fail the run."""
    indianapi = FakeFinancialProvider(_financials())
    market_series = [_point("2026-09-01", "410")]
    yfinance = FakeMarketProvider(_snapshot(prices=market_series))
    screener = FakeHistoricalProvider(status=SourceStatus.AUTH_EXPIRED, detail="cookie rejected")
    manager = _manager(
        financial={INDIANAPI: indianapi}, market={YFINANCE: yfinance}, historical=screener
    )

    financials = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    snapshot = await manager.get_snapshot(TICKER)

    assert financials.status == "success"
    assert snapshot.status == "success"
    assert snapshot.snapshot.quote.current_price == Decimal("421.50")
    # Fell back to the market provider's own series.
    assert snapshot.snapshot.recent_prices == market_series
    assert manager.resolved_source(Category.HISTORICAL_PRICE) == YFINANCE
    assert manager.used_fallback(Category.HISTORICAL_PRICE)
    assert any("AUTH_EXPIRED" in w for w in snapshot.snapshot.warnings)


async def test_screener_health_records_the_auth_failure():
    screener = FakeHistoricalProvider(status=SourceStatus.AUTH_EXPIRED)
    manager = _manager(market={YFINANCE: FakeMarketProvider(_snapshot())}, historical=screener)
    await manager.get_snapshot(TICKER)
    health = manager._registry.health(SCREENER)
    assert health.status == SourceStatus.AUTH_EXPIRED
    assert health.last_error_at is not None


async def test_screener_not_configured_is_not_an_error_path():
    screener = FakeHistoricalProvider(status=SourceStatus.NOT_CONFIGURED)
    market_series = [_point("2026-09-01", "410")]
    manager = _manager(
        market={YFINANCE: FakeMarketProvider(_snapshot(prices=market_series))},
        historical=screener,
    )
    snapshot = await manager.get_snapshot(TICKER)
    assert snapshot.status == "success"
    assert snapshot.snapshot.recent_prices == market_series


# --- Scenario 3: IndianAPI unavailable ---------------------------------------


async def test_financial_primary_failure_falls_back_to_the_next_provider():
    indianapi = FakeFinancialProvider(
        _financial_error(FinancialDataErrorCode.PROVIDER_UNAVAILABLE)
    )
    fmp = FakeFinancialProvider(_financials())
    manager = _manager(financial={INDIANAPI: indianapi, FMP: fmp})

    result = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))

    assert result.status == "success"
    assert manager.resolved_source(Category.FINANCIALS) == FMP
    assert manager.used_fallback(Category.FINANCIALS)


async def test_a_crashing_provider_does_not_end_the_chain():
    indianapi = FakeFinancialProvider(raises=RuntimeError("boom"))
    fmp = FakeFinancialProvider(_financials())
    manager = _manager(financial={INDIANAPI: indianapi, FMP: fmp})
    result = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    assert result.status == "success"
    assert manager.resolved_source(Category.FINANCIALS) == FMP


async def test_all_financial_providers_failing_returns_a_structured_error():
    manager = _manager(
        financial={
            INDIANAPI: FakeFinancialProvider(
                _financial_error(FinancialDataErrorCode.PROVIDER_UNAVAILABLE)
            ),
            FMP: FakeFinancialProvider(_financial_error(FinancialDataErrorCode.RATE_LIMITED)),
        }
    )
    result = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    assert result.status == "error"
    assert result.error is not None
    assert manager.resolved_source(Category.FINANCIALS) is None


async def test_exhausted_chain_reports_the_primarys_error_not_the_last_fallbacks():
    """A nonexistent ticker should surface COMPANY_NOT_FOUND from the
    authoritative source, not RATE_LIMITED from whichever fallback was
    tried last."""
    manager = _manager(
        financial={
            INDIANAPI: FakeFinancialProvider(
                _financial_error(FinancialDataErrorCode.COMPANY_NOT_FOUND)
            ),
            FMP: FakeFinancialProvider(_financial_error(FinancialDataErrorCode.RATE_LIMITED)),
        }
    )
    result = await manager.get_company_financials(CompanyIdentifier(ticker="NOSUCHTICKER"))
    assert result.error.code == FinancialDataErrorCode.COMPANY_NOT_FOUND


async def test_no_capable_financial_provider_is_reported_not_crashed():
    """Screener cannot produce statements, so a Screener-only financial
    chain must return a structured error rather than attempting it."""
    screener = FakeFinancialProvider(_financials())
    manager = _manager(financial={SCREENER: screener}, financial_chain=[SCREENER])
    result = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    assert result.status == "error"
    assert screener.received_tickers == []


# --- Scenario 4: market provider unavailable ---------------------------------


async def test_market_primary_failure_falls_back_to_the_next_provider():
    yfinance = FakeMarketProvider(_market_error(MarketDataErrorCode.PROVIDER_UNAVAILABLE))
    fmp = FakeMarketProvider(_snapshot())
    manager = _manager(market={YFINANCE: yfinance, FMP: fmp})

    result = await manager.get_snapshot(TICKER, include_recent_prices=False)

    assert result.status == "success"
    assert manager.resolved_source(Category.MARKET_QUOTE) == FMP
    assert manager.used_fallback(Category.MARKET_QUOTE)


async def test_market_failure_does_not_affect_financial_retrieval():
    indianapi = FakeFinancialProvider(_financials())
    manager = _manager(
        financial={INDIANAPI: indianapi},
        market={YFINANCE: FakeMarketProvider(raises=RuntimeError("market down"))},
    )

    snapshot = await manager.get_snapshot(TICKER, include_recent_prices=False)
    financials = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))

    assert snapshot.status == "error"
    assert financials.status == "success"


async def test_financial_failure_does_not_affect_quote_retrieval():
    manager = _manager(
        financial={INDIANAPI: FakeFinancialProvider(raises=RuntimeError("indianapi down"))},
        market={YFINANCE: FakeMarketProvider(_snapshot())},
    )

    financials = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    snapshot = await manager.get_snapshot(TICKER, include_recent_prices=False)

    assert financials.status == "error"
    assert snapshot.status == "success"


async def test_every_market_provider_failing_returns_a_structured_error():
    manager = _manager(
        market={
            YFINANCE: FakeMarketProvider(_market_error(MarketDataErrorCode.TICKER_NOT_FOUND)),
            FMP: FakeMarketProvider(_market_error(MarketDataErrorCode.PROVIDER_UNAVAILABLE)),
        }
    )
    result = await manager.get_snapshot(TICKER, include_recent_prices=False)
    assert result.status == "error"
    assert result.error is not None


# --- Scenario 5: sources are not mixed within a category ---------------------


async def test_each_category_records_its_own_source_independently():
    manager = _manager(
        financial={INDIANAPI: FakeFinancialProvider(_financials())},
        market={YFINANCE: FakeMarketProvider(_snapshot(prices=[_point("2026-09-01", "410")]))},
        historical=FakeHistoricalProvider(points=[_point("2026-09-02", "421.50")]),
    )
    await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    await manager.get_snapshot(TICKER)

    assert manager.resolved_source(Category.FINANCIALS) == INDIANAPI
    assert manager.resolved_source(Category.MARKET_QUOTE) == YFINANCE
    assert manager.resolved_source(Category.HISTORICAL_PRICE) == SCREENER


async def test_unconfigured_provider_is_never_attempted():
    fmp = FakeFinancialProvider(_financials())
    manager = _manager(
        financial={FMP: fmp},
        configured={INDIANAPI: True, FMP: False, YFINANCE: True, SCREENER: True},
    )
    result = await manager.get_company_financials(CompanyIdentifier(ticker=TICKER))
    assert fmp.received_tickers == []
    assert result.status == "error"


# --- Primary-source-wins merge rule ------------------------------------------


async def test_provenance_must_be_snapshotted_because_a_later_call_overwrites_it():
    """One research run fetches the market snapshot twice. Reading
    provenance back later would report the second call's attempts, so
    callers snapshot it immediately after their own call."""
    failing_then_working = FakeMarketProvider(_snapshot())
    manager = _manager(
        market={YFINANCE: FakeMarketProvider(_market_error(MarketDataErrorCode.TICKER_NOT_FOUND)), FMP: failing_then_working}
    )

    await manager.get_snapshot(TICKER, include_recent_prices=False)
    captured = manager.provenance_snapshot()

    assert captured[Category.MARKET_QUOTE.value]["source"] == FMP
    assert captured[Category.MARKET_QUOTE.value]["fallback_used"] is True
    assert captured[Category.MARKET_QUOTE.value]["attempts"] == [
        "yfinance=UNAVAILABLE",
        "fmp=SUCCESS",
    ]

    # A second call overwrites live state; the captured snapshot does not move.
    manager._market_providers = {YFINANCE: FakeMarketProvider(_snapshot())}
    await manager.get_snapshot(TICKER, include_recent_prices=False)
    assert manager.resolved_source(Category.MARKET_QUOTE) == YFINANCE
    assert captured[Category.MARKET_QUOTE.value]["source"] == FMP


async def test_get_quote_skips_history_for_portfolio_callers():
    yfinance = FakeMarketProvider(_snapshot(prices=[_point("2026-09-01", "410")]))
    screener = FakeHistoricalProvider(points=[_point("2026-09-02", "421.50")])
    manager = _manager(market={YFINANCE: yfinance}, historical=screener)

    result = await manager.get_quote(TICKER)

    assert result.status == "success"
    # No historical resolution happens for a plain quote.
    assert screener.calls == 0


async def test_historical_source_is_reported_as_the_provider_that_actually_served_it():
    """With no Screener primary available, the series came from the market
    provider -- provenance must name that provider, not the configured
    chain head."""
    fmp = FakeMarketProvider(_snapshot(prices=[_point("2026-09-01", "410")]))
    manager = _manager(
        market={FMP: fmp},
        market_chain=[FMP],
        historical_chain=[YFINANCE, FMP],
    )
    await manager.get_snapshot(TICKER)
    assert manager.resolved_source(Category.HISTORICAL_PRICE) == FMP


# --- Scenario 6: quote provider fails entirely, but Screener still has historical data ---


async def test_historical_data_is_still_fetched_when_every_quote_provider_fails():
    """A ticker delisted from (or never listed on) yfinance but still
    tracked on Screener must still get technical/forecast signals --
    Screener's chart fetch doesn't need a live quote to exist."""
    yfinance = FakeMarketProvider(_market_error(MarketDataErrorCode.TICKER_NOT_FOUND))
    screener = FakeHistoricalProvider(points=[_point("2026-09-01", "410"), _point("2026-09-02", "415")])
    manager = _manager(market={YFINANCE: yfinance}, historical=screener)

    result = await manager.get_snapshot(TICKER)

    assert result.status == "success"
    assert result.snapshot is not None
    assert result.snapshot.quote is None
    assert [p.timestamp for p in result.snapshot.recent_prices] == ["2026-09-01", "2026-09-02"]
    assert "Live quote unavailable" in result.snapshot.warnings[0]


async def test_still_reports_the_original_error_when_both_quote_and_historical_fail():
    yfinance = FakeMarketProvider(_market_error(MarketDataErrorCode.TICKER_NOT_FOUND))
    screener = FakeHistoricalProvider(status=SourceStatus.UNAVAILABLE)
    manager = _manager(market={YFINANCE: yfinance}, historical=screener)

    result = await manager.get_snapshot(TICKER)

    assert result.status == "error"
    assert screener.calls == 1  # still attempted, just found nothing either


async def test_historical_fetch_is_skipped_when_include_recent_prices_is_false_even_on_quote_failure():
    yfinance = FakeMarketProvider(_market_error(MarketDataErrorCode.TICKER_NOT_FOUND))
    screener = FakeHistoricalProvider(points=[_point("2026-09-01", "410")])
    manager = _manager(market={YFINANCE: yfinance}, historical=screener)

    result = await manager.get_snapshot(TICKER, include_recent_prices=False)

    assert result.status == "error"
    assert screener.calls == 0


async def test_no_configured_quote_provider_at_all_still_gets_historical_data():
    screener = FakeHistoricalProvider(points=[_point("2026-09-01", "410")])
    manager = _manager(market={}, historical=screener)

    result = await manager.get_snapshot(TICKER)

    assert result.status == "success"
    assert result.snapshot.quote is None
    assert len(result.snapshot.recent_prices) == 1


def test_primary_source_wins_for_a_shared_date():
    primary = [_point("2026-09-01", "421.50"), _point("2026-09-02", "425.00")]
    secondary = [_point("2026-09-01", "999.99"), _point("2026-09-03", "430.00")]

    merged = merge_by_primary([(SCREENER, primary), (YFINANCE, secondary)])

    by_date = {p.timestamp: p.close for p in merged}
    # The primary owns 09-01; the secondary only fills the date it didn't cover.
    assert by_date["2026-09-01"] == Decimal("421.50")
    assert by_date["2026-09-03"] == Decimal("430.00")
    assert len(merged) == 3


def test_merge_is_chronological_and_deterministic():
    a = [_point("2026-09-03", "3")]
    b = [_point("2026-09-01", "1"), _point("2026-09-02", "2")]
    merged = merge_by_primary([(SCREENER, a), (YFINANCE, b)])
    assert [p.timestamp for p in merged] == ["2026-09-01", "2026-09-02", "2026-09-03"]
