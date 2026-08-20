import pytest

from app.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider="local",
        local_llm_base_url="http://test-llm-server:8080/v1",
        local_llm_model="test-model",
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
    )
