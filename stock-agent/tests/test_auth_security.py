import jwt
import pytest

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_never_stores_plaintext():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert "correct-horse-battery" not in hashed


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_handles_garbage_hash_safely():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_hash_password_is_salted_differently_each_time():
    assert hash_password("same-password") != hash_password("same-password")


def test_create_access_token_round_trips_via_decode():
    token, jti = create_access_token("user-123", "secret", "HS256", expires_minutes=60)
    payload = decode_access_token(token, "secret", "HS256")
    assert payload["sub"] == "user-123"
    assert payload["jti"] == jti


def test_decode_access_token_rejects_wrong_secret():
    token, _ = create_access_token("user-123", "secret", "HS256", expires_minutes=60)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, "wrong-secret", "HS256")


def test_create_access_token_uses_unique_jti_per_call():
    _, jti1 = create_access_token("user-123", "secret", "HS256", expires_minutes=60)
    _, jti2 = create_access_token("user-123", "secret", "HS256", expires_minutes=60)
    assert jti1 != jti2
