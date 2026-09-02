from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_returns_matches():
    response = client.get("/api/v1/search", params={"q": "TCS"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["symbol"] == "TCS"
    assert body[0]["exchange"] == "NSE"


def test_search_requires_query_param():
    response = client.get("/api/v1/search")
    assert response.status_code == 422


def test_search_respects_limit_param():
    response = client.get("/api/v1/search", params={"q": "A", "limit": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_search_unknown_query_returns_empty_list():
    response = client.get("/api/v1/search", params={"q": "ZZZZZZNOTATICKERZZZZZZ"})
    assert response.status_code == 200
    assert response.json() == []


def test_search_rejects_limit_out_of_range():
    response = client.get("/api/v1/search", params={"q": "TCS", "limit": 100})
    assert response.status_code == 422
