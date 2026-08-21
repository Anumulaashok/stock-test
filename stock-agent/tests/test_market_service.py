import pytest

from app.market.base import MarketDataProvider
from app.market.exceptions import MarketProviderError
from app.market.service import MarketDataService
from app.models.market import (
    HistoricalPricePoint,
    MarketDataErrorCode,
    MarketQuote,
    MarketStatus,
    PriceFreshness,
)


def _quote(ticker: str = "AAPL") -> MarketQuote:
    return MarketQuote(
        ticker=ticker,
        current_price=None,
        previous_close=None,
        change=None,
        change_percent=None,
        currency=None,
        market_status=MarketStatus.UNKNOWN,
        market_timestamp=None,
        data_timestamp="2026-08-21T00:00:00+00:00",
        freshness=PriceFreshness.UNAVAILABLE,
        source="stub",
    )


class _StubProvider(MarketDataProvider):
    def __init__(self, quote_result=None, quote_error=None, prices_result=None, prices_error=None):
        self._quote_result = quote_result
        self._quote_error = quote_error
        self._prices_result = prices_result if prices_result is not None else []
        self._prices_error = prices_error

    async def get_quote(self, ticker: str) -> MarketQuote:
        if self._quote_error:
            raise self._quote_error
        return self._quote_result

    async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
        if self._prices_error:
            raise self._prices_error
        return self._prices_result


@pytest.mark.asyncio
async def test_get_snapshot_success():
    quote = _quote()
    provider = _StubProvider(quote_result=quote, prices_result=[])
    result = await MarketDataService(provider).get_snapshot("AAPL")
    assert result.status == "success"
    assert result.snapshot.quote == quote
    assert result.snapshot.recent_prices == []
    assert result.snapshot.warnings == []


@pytest.mark.asyncio
async def test_get_snapshot_quote_failure_fails_the_whole_call():
    error = MarketProviderError(MarketDataErrorCode.TICKER_NOT_FOUND, "not found")
    provider = _StubProvider(quote_error=error)
    result = await MarketDataService(provider).get_snapshot("BOGUS")
    assert result.status == "error"
    assert result.error.code == MarketDataErrorCode.TICKER_NOT_FOUND
    assert result.snapshot is None


@pytest.mark.asyncio
async def test_get_snapshot_recent_prices_failure_is_non_fatal():
    quote = _quote()
    error = MarketProviderError(MarketDataErrorCode.PROVIDER_UNAVAILABLE, "history unavailable")
    provider = _StubProvider(quote_result=quote, prices_error=error)
    result = await MarketDataService(provider).get_snapshot("AAPL")
    assert result.status == "success"
    assert result.snapshot.quote == quote
    assert result.snapshot.recent_prices == []
    assert any("history unavailable" in w for w in result.snapshot.warnings)


@pytest.mark.asyncio
async def test_get_snapshot_can_skip_recent_prices():
    quote = _quote()
    provider = _StubProvider(quote_result=quote)
    result = await MarketDataService(provider).get_snapshot("AAPL", include_recent_prices=False)
    assert result.status == "success"
    assert result.snapshot.recent_prices == []


@pytest.mark.asyncio
async def test_get_quote_convenience_method_skips_recent_prices():
    quote = _quote()
    calls = {"prices": 0}

    class _CountingProvider(_StubProvider):
        async def get_recent_prices(self, ticker: str, limit: int) -> list[HistoricalPricePoint]:
            calls["prices"] += 1
            return []

    result = await MarketDataService(_CountingProvider(quote_result=quote)).get_quote("AAPL")
    assert result.status == "success"
    assert calls["prices"] == 0
