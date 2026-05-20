from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app
from src._core.config import settings


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


async def _register(client: AsyncClient, suffix: str) -> dict:
    response = await client.post(
        "/v1/auth/register",
        json={
            "username": f"auth{suffix}",
            "fullName": "Auth E2E",
            "email": f"auth{suffix}@example.com",
            "password": "secret",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_register_login_me_refresh_and_logout():
    async with _client() as client:
        registered = await _register(client, "flow")
        access_token = registered["accessToken"]
        refresh_token = registered["refreshToken"]

        me = await client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        login = await client.post(
            "/v1/auth/login",
            json={"username": "authflow", "password": "secret"},
        )
        refresh = await client.post(
            "/v1/auth/refresh",
            json={"refreshToken": refresh_token},
        )
        reused = await client.post(
            "/v1/auth/refresh",
            json={"refreshToken": refresh_token},
        )
        next_refresh = refresh.json()["data"]["refreshToken"]
        logout = await client.post(
            "/v1/auth/logout",
            json={"refreshToken": next_refresh},
        )
        after_logout = await client.post(
            "/v1/auth/refresh",
            json={"refreshToken": next_refresh},
        )

    assert me.status_code == 200
    assert me.json()["data"]["username"] == "authflow"
    assert "password" not in me.json()["data"]
    assert "role" not in me.json()["data"]
    assert login.status_code == 200
    assert refresh.status_code == 200
    assert "role" not in registered["user"]
    assert "role" not in login.json()["data"]["user"]
    assert "role" not in refresh.json()["data"]["user"]
    assert reused.status_code == 401
    assert reused.json()["errorCode"] == "REFRESH_TOKEN_REVOKED"
    assert logout.status_code == 200
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_invalid_password_and_missing_token_return_401():
    async with _client() as client:
        await _register(client, "badpw")
        login = await client.post(
            "/v1/auth/login",
            json={"username": "authbadpw", "password": "wrong"},
        )
        me = await client.get("/v1/auth/me")

    assert login.status_code == 401
    assert login.json()["errorCode"] == "INVALID_CREDENTIALS"
    assert me.status_code == 401
    assert me.json()["errorCode"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_does_not_reveal_whether_username_exists():
    async with _client() as client:
        await _register(client, "enum")
        bad_password = await client.post(
            "/v1/auth/login",
            json={"username": "authenum", "password": "wrong"},
        )
        missing_user = await client.post(
            "/v1/auth/login",
            json={"username": "authmissing", "password": "wrong"},
        )

    assert bad_password.status_code == 401
    assert missing_user.status_code == 401
    assert bad_password.json() == missing_user.json()


@pytest.mark.asyncio
async def test_register_duplicate_returns_unique_field_errors():
    payload = {
        "username": "authduplicate",
        "fullName": "Auth Duplicate",
        "email": "authduplicate@example.com",
        "password": "secret",
    }

    async with _client() as client:
        first = await client.post("/v1/auth/register", json=payload)
        second = await client.post("/v1/auth/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["errorCode"] == "USER_ALREADY_EXISTS"
    assert second.json()["errorDetails"]["errors"] == [
        {
            "field": "username",
            "message": "username already exists",
            "type": "unique",
        },
        {
            "field": "email",
            "message": "email already exists",
            "type": "unique",
        },
    ]


@pytest.mark.asyncio
async def test_expired_refresh_token_returns_401():
    now = datetime.now(UTC)
    expired_refresh_token = jwt.encode(
        {
            "sub": "1",
            "jti": "expired-e2e-refresh",
            "type": "refresh",
            "iat": now - timedelta(days=2),
            "exp": now - timedelta(days=1),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    async with _client() as client:
        response = await client.post(
            "/v1/auth/refresh",
            json={"refreshToken": expired_refresh_token},
        )

    assert response.status_code == 401
    assert response.json()["errorCode"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_user_endpoint():
    async with _client() as client:
        registered = await _register(client, "type")
        response = await client.get(
            "/v1/users",
            headers={"Authorization": f"Bearer {registered['refreshToken']}"},
        )

    assert response.status_code == 401
    assert response.json()["errorCode"] == "INVALID_TOKEN"
