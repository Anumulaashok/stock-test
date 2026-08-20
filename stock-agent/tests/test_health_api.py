from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_llm_reports_misconfigured_when_unset(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        response = client.get("/health/llm")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "misconfigured"
        assert "api_key" not in body
    finally:
        get_settings.cache_clear()
