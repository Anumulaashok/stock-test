import pytest

from app.core.config import Settings
from app.market.factory import get_market_data_provider
from app.market.providers.fmp import FMPMarketProvider


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_fmp_provider_selected_by_identifier():
    provider = get_market_data_provider(_settings(market_data_provider="fmp", fmp_api_key="key"))
    assert isinstance(provider, FMPMarketProvider)


def test_provider_identifier_is_case_insensitive():
    provider = get_market_data_provider(_settings(market_data_provider="FMP", fmp_api_key="key"))
    assert isinstance(provider, FMPMarketProvider)


def test_unknown_provider_raises_clear_configuration_error():
    with pytest.raises(ValueError, match="Unsupported MARKET_DATA_PROVIDER: 'abc'"):
        get_market_data_provider(_settings(market_data_provider="abc"))


def test_missing_fmp_api_key_raises_when_fmp_selected():
    with pytest.raises(ValueError, match="FMP_API_KEY"):
        get_market_data_provider(_settings(market_data_provider="fmp", fmp_api_key=None))
