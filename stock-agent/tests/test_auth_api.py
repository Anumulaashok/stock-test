def _signup(db_client, email="alice@example.com", password="correct-horse"):
    return db_client.post("/api/v1/auth/signup", json={"email": email, "password": password})


def test_signup_creates_user_and_returns_token(db_client):
    response = _signup(db_client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.com"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_signup_duplicate_email_is_rejected(db_client):
    _signup(db_client)
    response = _signup(db_client)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_signup_rejects_invalid_email(db_client):
    response = _signup(db_client, email="not-an-email")
    assert response.status_code == 400


def test_signup_rejects_short_password(db_client):
    response = db_client.post(
        "/api/v1/auth/signup", json={"email": "bob@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_login_with_correct_credentials_succeeds(db_client):
    _signup(db_client)
    response = db_client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "correct-horse"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_rejected(db_client):
    _signup(db_client)
    response = db_client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_login_with_unknown_email_gives_identical_error(db_client):
    response = db_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_me_requires_authentication(db_client):
    response = db_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_authenticated_user(db_client):
    token = _signup(db_client).json()["access_token"]
    response = db_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_rejects_garbage_token(db_client):
    response = db_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_logout_revokes_token(db_client):
    token = _signup(db_client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = db_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    me_response = db_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401


def test_logout_without_token_is_unauthorized(db_client):
    response = db_client.post("/api/v1/auth/logout")
    assert response.status_code == 401
