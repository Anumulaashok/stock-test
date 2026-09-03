"""HTTP-level test for `GET /api/v1/sectors` -- only the misconfigured-
provider path, which needs no external mocking (mirrors the same
pattern used for `/qa/ticker` and `/research/ticker` when
`FINANCIAL_DATA_PROVIDER` isn't set). Full multi-ticker scoring is
covered by `tests/test_sector_ranking_service.py` against a fake
application service."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _db_override(db_dependency_override):
    pass


def test_get_sectors_returns_unavailable_when_provider_misconfigured(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    response = client.get("/api/v1/sectors")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["sectors"] == []

    get_settings.cache_clear()
