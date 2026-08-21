import pytest

from app.core.config import Settings
from app.data.factory import get_financial_data_provider
from app.data.providers.fmp import FMPProvider
from app.data.providers.indianapi import IndianAPIProvider


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_fmp_provider_selected_by_identifier():
    provider = get_financial_data_provider(_settings(financial_data_provider="fmp", fmp_api_key="key"))
    assert isinstance(provider, FMPProvider)


def test_indianapi_provider_selected_by_identifier():
    provider = get_financial_data_provider(
        _settings(financial_data_provider="indianapi", indian_api_key="key")
    )
    assert isinstance(provider, IndianAPIProvider)


def test_provider_identifier_is_case_insensitive():
    provider = get_financial_data_provider(_settings(financial_data_provider="FMP", fmp_api_key="key"))
    assert isinstance(provider, FMPProvider)


def test_unknown_provider_raises_clear_configuration_error():
    with pytest.raises(ValueError, match="Unsupported FINANCIAL_DATA_PROVIDER: 'abc'"):
        get_financial_data_provider(_settings(financial_data_provider="abc"))


def test_url_used_as_provider_name_raises_clear_unsupported_error():
    # The exact bug this refactor fixes: a base URL was mistakenly put
    # into FINANCIAL_DATA_PROVIDER instead of a provider identifier.
    with pytest.raises(ValueError) as exc_info:
        get_financial_data_provider(_settings(financial_data_provider="https://stock.indianapi.in"))
    message = str(exc_info.value)
    assert "Unsupported FINANCIAL_DATA_PROVIDER: 'https://stock.indianapi.in'" in message
    assert "not a URL" in message
    assert "fmp" in message and "indianapi" in message


def test_missing_fmp_config_while_selecting_indianapi_does_not_fail():
    # No FMP_API_KEY set at all -- selecting indianapi must not care.
    provider = get_financial_data_provider(
        _settings(financial_data_provider="indianapi", indian_api_key="key", fmp_api_key=None)
    )
    assert isinstance(provider, IndianAPIProvider)


def test_missing_indianapi_config_while_selecting_fmp_does_not_fail():
    provider = get_financial_data_provider(
        _settings(financial_data_provider="fmp", fmp_api_key="key", indian_api_key=None)
    )
    assert isinstance(provider, FMPProvider)


def test_missing_fmp_api_key_raises_when_fmp_selected():
    with pytest.raises(ValueError, match="FMP_API_KEY"):
        get_financial_data_provider(_settings(financial_data_provider="fmp", fmp_api_key=None))


def test_missing_indian_api_key_raises_when_indianapi_selected():
    with pytest.raises(ValueError, match="INDIAN_API_KEY"):
        get_financial_data_provider(_settings(financial_data_provider="indianapi", indian_api_key=None))
