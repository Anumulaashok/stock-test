from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.market.exceptions import MarketProviderError
from app.market.providers.yfinance_client import YFinanceClient
from app.models.market import MarketDataErrorCode


class _FastInfo(dict):
    """yfinance's real `FastInfo` is dict-like (supports `dict(fast_info)`)
    but not a plain dict -- mirror that here instead of using one."""


@pytest.mark.asyncio
async def test_get_fast_info_returns_plain_dict():
    fake_ticker = MagicMock()
    fake_ticker.fast_info = _FastInfo(lastPrice=1302.5, previousClose=1313.1, marketCap=1.0, currency="INR")
    with patch("app.market.providers.yfinance_client.yf.Ticker", return_value=fake_ticker):
        data = await YFinanceClient().get_fast_info("RELIANCE.NS")
    assert data["lastPrice"] == 1302.5
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_fast_info_raises_ticker_not_found_when_no_price():
    fake_ticker = MagicMock()
    fake_ticker.fast_info = _FastInfo(currency="INR")
    with patch("app.market.providers.yfinance_client.yf.Ticker", return_value=fake_ticker):
        with pytest.raises(MarketProviderError) as exc_info:
            await YFinanceClient().get_fast_info("NOPE.NS")
    assert exc_info.value.code == MarketDataErrorCode.TICKER_NOT_FOUND


@pytest.mark.asyncio
async def test_get_fast_info_translates_unexpected_error():
    fake_ticker = MagicMock()
    type(fake_ticker).fast_info = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    with patch("app.market.providers.yfinance_client.yf.Ticker", return_value=fake_ticker):
        with pytest.raises(MarketProviderError) as exc_info:
            await YFinanceClient().get_fast_info("RELIANCE.NS")
    assert exc_info.value.code == MarketDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_get_history_maps_dataframe_rows_to_dicts():
    index = pd.to_datetime(["2026-09-01", "2026-09-02"]).tz_localize("Asia/Kolkata")
    df = pd.DataFrame(
        {"Open": [1285.0, 1298.0], "High": [1311.8, 1321.9], "Low": [1280.0, 1290.0], "Close": [1298.0, 1313.1], "Volume": [10_000_000, 12_000_000]},
        index=index,
    )
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = df
    with patch("app.market.providers.yfinance_client.yf.Ticker", return_value=fake_ticker):
        records = await YFinanceClient().get_history("RELIANCE.NS", period="1y")
    assert len(records) == 2
    assert records[0]["open"] == 1285.0
    assert records[0]["volume"] == 10_000_000
    assert records[0]["date"].startswith("2026-09-01")
