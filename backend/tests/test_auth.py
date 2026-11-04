from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.security import create_access_token
from tests.conftest import register


def test_register_returns_token_and_user(client: TestClient) -> None:
    res = client.post(
        "/api/auth/register", json={"email": "Ada@Example.com", "password": "longenough"}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["created_at"].endswith("Z")


def test_duplicate_email_conflicts(client: TestClient) -> None:
    register(client, "dup@example.com")
    res = client.post(
        "/api/auth/register", json={"email": "DUP@example.com", "password": "longenough"}
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


def test_short_password_is_rejected_with_envelope(client: TestClient) -> None:
    res = client.post("/api/auth/register", json={"email": "a@b.co", "password": "short"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_invalid_email_is_rejected(client: TestClient) -> None:
    res = client.post("/api/auth/register", json={"email": "nope", "password": "longenough"})
    assert res.status_code == 422
    assert "email" in res.json()["error"]["message"].lower()


def test_login_success_and_me(client: TestClient) -> None:
    register(client, "ada@example.com")
    res = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "correct horse"}
    )
    assert res.status_code == 200
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}
    )
    assert me.status_code == 200 and me.json()["email"] == "ada@example.com"


def test_bad_password_is_unauthorized(client: TestClient) -> None:
    register(client, "ada@example.com")
    res = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "wrong password"}
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_unknown_email_is_unauthorized(client: TestClient) -> None:
    res = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever123"}
    )
    assert res.status_code == 401


def test_protected_route_requires_token(client: TestClient) -> None:
    for method, path in [
        ("get", "/api/documents"),
        ("get", "/api/sessions"),
        ("get", "/api/stats"),
    ]:
        res = getattr(client, method)(path)
        assert res.status_code == 401, path
        assert res.json()["error"]["code"] == "unauthorized"


def test_garbage_token_is_unauthorized(client: TestClient) -> None:
    res = client.get("/api/documents", headers={"Authorization": "Bearer not.a.token"})
    assert res.status_code == 401


def test_expired_token_is_unauthorized(client: TestClient) -> None:
    headers = register(client)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    expired = create_access_token(
        user_id, Settings(jwt_secret="test-secret-test-secret-test-secret", jwt_expire_minutes=-5)
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401
    assert "expired" in res.json()["error"]["message"].lower()
