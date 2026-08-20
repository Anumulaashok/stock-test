import json

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
async def test_generate_sends_bearer_token_and_chat_template_kwargs():
    provider = LocalLLMProvider(
        base_url="http://test-llm:8080/v1",
        model="qwen3-8b",
        api_key="secret-key",
        enable_thinking=False,
    )
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}}]}
        )
    )

    await provider.generate("hi", max_tokens=32)

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer secret-key"
    body = json.loads(request.content)
    assert body["model"] == "qwen3-8b"
    assert body["max_tokens"] == 32
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
@respx.mock
async def test_generate_sends_system_prompt_as_separate_message():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="qwen3-8b")
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    await provider.generate("do the task", system_prompt="you are an analyst")

    body = json.loads(route.calls.last.request.content)
    assert body["messages"] == [
        {"role": "system", "content": "you are an analyst"},
        {"role": "user", "content": "do the task"},
    ]


@pytest.mark.asyncio
@respx.mock
async def test_generate_without_system_prompt_sends_only_user_message():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="qwen3-8b")
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    await provider.generate("do the task")

    body = json.loads(route.calls.last.request.content)
    assert body["messages"] == [{"role": "user", "content": "do the task"}]


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
async def test_generate_raises_on_unauthorized():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )

    with pytest.raises(LLMProviderError):
        await provider.generate("hi")


@pytest.mark.asyncio
@respx.mock
async def test_generate_raises_on_empty_content():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
    )

    with pytest.raises(LLMProviderError):
        await provider.generate("hi")


@pytest.mark.asyncio
@respx.mock
async def test_health_check_true_when_reachable():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "Remote AI connection works."}}]}
        )
    )

    assert await provider.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_when_server_unavailable():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    assert await provider.health_check() is False
