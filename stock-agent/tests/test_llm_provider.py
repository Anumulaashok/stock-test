import httpx
import pytest
import respx

from app.llm.base import LLMProviderError
from app.llm.factory import get_llm_provider
from app.llm.local_provider import LocalLLMProvider


def test_local_provider_requires_base_url():
    with pytest.raises(ValueError):
        LocalLLMProvider(base_url="", model="test-model")


def test_local_provider_requires_model():
    with pytest.raises(ValueError):
        LocalLLMProvider(base_url="http://example:8000/v1", model="")


def test_factory_builds_local_provider(settings):
    provider = get_llm_provider(settings)
    assert isinstance(provider, LocalLLMProvider)


def test_factory_raises_when_local_config_missing():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        get_llm_provider(Settings(_env_file=None, llm_provider="local"))


def test_factory_raises_for_unsupported_provider(settings):
    settings.llm_provider = "openai"
    with pytest.raises(ValueError):
        get_llm_provider(settings)


@pytest.mark.asyncio
@respx.mock
async def test_generate_returns_message_content():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}}]}
        )
    )

    result = await provider.generate("hi")
    assert result == "hello"


@pytest.mark.asyncio
@respx.mock
async def test_generate_raises_on_timeout():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    with pytest.raises(LLMProviderError):
        await provider.generate("hi")


@pytest.mark.asyncio
@respx.mock
async def test_health_check_true_when_reachable():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.get("http://test-llm:8080/v1/models").mock(return_value=httpx.Response(200, json={}))

    assert await provider.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_when_server_unavailable():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.get("http://test-llm:8080/v1/models").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    assert await provider.health_check() is False
