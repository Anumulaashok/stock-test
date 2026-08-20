import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_llm_reports_misconfigured_when_unset(monkeypatch):
    # Explicit empty overrides, not delenv: os.environ takes priority over
    # a local .env file in pydantic-settings, so this is what actually
    # unsets these fields even when a real .env is present on disk.
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")

    get_settings.cache_clear()
    try:
        response = client.get("/health/llm")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "misconfigured"
        assert "api_key" not in body
    finally:
        get_settings.cache_clear()


@respx.mock
def test_health_llm_reports_ok_and_never_leaks_api_key(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "super-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Remote AI connection works."}}]},
        )
    )

    get_settings.cache_clear()
    try:
        response = client.get("/health/llm")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["response"] == "Remote AI connection works."
        assert "super-secret-key" not in response.text
    finally:
        get_settings.cache_clear()


@respx.mock
def test_health_llm_reports_unreachable_on_connection_failure(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://test-llm:8080/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "super-secret-key")

    respx.post("http://test-llm:8080/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    get_settings.cache_clear()
    try:
        response = client.get("/health/llm")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unreachable"
        assert "super-secret-key" not in response.text
    finally:
        get_settings.cache_clear()
