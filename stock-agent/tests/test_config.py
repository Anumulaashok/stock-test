from app.core.config import Settings


def test_settings_defaults_to_local_provider():
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "local"


def test_settings_reads_llm_fields():
    settings = Settings(
        _env_file=None,
        local_llm_base_url="http://example:8000/v1",
        local_llm_model="qwen-test",
    )
    assert settings.local_llm_base_url == "http://example:8000/v1"
    assert settings.local_llm_model == "qwen-test"


def test_settings_never_hardcodes_credentials():
    settings = Settings(_env_file=None)
    assert settings.local_llm_base_url is None
    assert settings.local_llm_api_key is None


# --- market_provider_chain: automatic fallback for a single configured provider ---


def test_market_chain_falls_back_to_indianapi_and_fmp_when_only_yfinance_is_configured():
    settings = Settings(_env_file=None, market_data_provider="yfinance")
    assert settings.market_provider_chain() == ["yfinance", "indianapi", "fmp"]


def test_market_chain_puts_yfinance_and_indianapi_before_fmp_when_fmp_is_the_singular_default():
    settings = Settings(_env_file=None, market_data_provider="fmp")
    assert settings.market_provider_chain() == ["yfinance", "indianapi", "fmp"]


def test_market_chain_puts_indianapi_configured_singular_first():
    settings = Settings(_env_file=None, market_data_provider="indianapi")
    assert settings.market_provider_chain() == ["indianapi", "yfinance", "fmp"]


def test_market_chain_respects_an_explicit_chain_override():
    settings = Settings(_env_file=None, market_data_provider="yfinance", market_data_providers="indianapi")
    assert settings.market_provider_chain() == ["indianapi"]
