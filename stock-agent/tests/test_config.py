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
