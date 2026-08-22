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


def test_factory_wires_reasoning_mode_from_settings(settings):
    settings.llm_provider = "nvidia"
    settings.local_llm_reasoning_mode = "reasoning_effort"
    settings.local_llm_reasoning_effort = "low"
    settings.local_llm_json_mode = True
    provider = get_llm_provider(settings)
    assert provider._reasoning_mode == "reasoning_effort"
    assert provider._reasoning_effort == "low"
    assert provider._json_mode is True


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
async def test_generate_sends_reasoning_effort_in_reasoning_effort_mode():
    provider = LocalLLMProvider(
        base_url="http://test-llm:8080/v1",
        model="openai/gpt-oss-20b",
        reasoning_mode="reasoning_effort",
        reasoning_effort="low",
    )
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    # A per-call enable_thinking override must be ignored in this mode --
    # the backend doesn't understand that key at all.
    await provider.generate("hi", enable_thinking=False)

    body = json.loads(route.calls.last.request.content)
    assert body["chat_template_kwargs"] == {"reasoning_effort": "low"}


@pytest.mark.asyncio
@respx.mock
async def test_generate_sends_response_format_when_json_mode_enabled():
    provider = LocalLLMProvider(
        base_url="http://test-llm:8080/v1", model="test-model", json_mode=True
    )
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    await provider.generate("hi")

    body = json.loads(route.calls.last.request.content)
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
@respx.mock
async def test_generate_omits_response_format_when_json_mode_disabled():
    provider = LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model")
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    await provider.generate("hi")

    body = json.loads(route.calls.last.request.content)
    assert "response_format" not in body


@pytest.mark.asyncio
@respx.mock
async def test_generate_sends_no_chat_template_kwargs_in_none_mode():
    provider = LocalLLMProvider(
        base_url="http://test-llm:8080/v1", model="test-model", reasoning_mode="none"
    )
    route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})
    )

    await provider.generate("hi")

    body = json.loads(route.calls.last.request.content)
    assert "chat_template_kwargs" not in body


def test_local_provider_rejects_unsupported_reasoning_mode():
    with pytest.raises(ValueError):
        LocalLLMProvider(base_url="http://test-llm:8080/v1", model="test-model", reasoning_mode="bogus")


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
