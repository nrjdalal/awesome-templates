"""End-to-end tests for the admin auth API (/v1/admin/*, ADR 049 admin realm)."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from src._apps.server.app import app
from src._core.common.security import hash_password
from src.admin_identity.domain.dtos.admin_identity_dto import CreateAdminAccountDTO


class _BootstrapSeed(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    is_bootstrap_admin: bool = True


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


async def _seed_real_admin(username: str, password: str) -> int:
    service = app.state.container.admin_identity_container.admin_identity_service()
    created = await service.create_admin_account(
        CreateAdminAccountDTO(
            username=username,
            full_name="Real Admin",
            email=f"{username}@example.com",
            permissions=["user"],
        ),
        temp_password="TempPass12345",  # noqa: S106  # gitleaks:allow
    )
    await service.change_admin_password(created.id, password)
    return created.id


async def _seed_bootstrap_admin(username: str, password: str) -> None:
    service = app.state.container.admin_identity_container.admin_identity_service()
    await service._admin_repository.insert_data(
        _BootstrapSeed(
            username=username,
            full_name="Bootstrap",
            email=f"{username}@example.com",
            password=hash_password(password),
        )
    )


@pytest.mark.asyncio
async def test_admin_login_refresh_logout_flow():
    await _seed_real_admin("flowadmin", "RealAdminPass123")

    async with _client() as client:
        login = await client.post(
            "/v1/admin/login",
            json={"username": "flowadmin", "password": "RealAdminPass123"},
        )
        assert login.status_code == 200, login.text
        data = login.json()["data"]
        assert data["tokenType"] == "bearer"
        assert data["admin"]["username"] == "flowadmin"
        assert "password" not in data["admin"]

        refresh = await client.post(
            "/v1/admin/refresh", json={"refreshToken": data["refreshToken"]}
        )
        assert refresh.status_code == 200, refresh.text
        new_refresh = refresh.json()["data"]["refreshToken"]

        logout = await client.post(
            "/v1/admin/logout", json={"refreshToken": new_refresh}
        )
        assert logout.status_code == 200
        assert logout.json()["data"] is True


@pytest.mark.asyncio
async def test_admin_token_is_rejected_on_customer_route():
    """Reverse trust boundary: an admin-realm token must NOT authenticate on a
    customer route (/v1/auth/me) — it fails the customer verifier."""
    await _seed_real_admin("crossadmin", "RealAdminPass123")

    async with _client() as client:
        login = await client.post(
            "/v1/admin/login",
            json={"username": "crossadmin", "password": "RealAdminPass123"},
        )
        admin_token = login.json()["data"]["accessToken"]
        me = await client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert me.status_code == 401, me.text


@pytest.mark.asyncio
async def test_admin_login_rejects_wrong_password():
    await _seed_real_admin("pwadmin", "RealAdminPass123")

    async with _client() as client:
        resp = await client.post(
            "/v1/admin/login",
            json={"username": "pwadmin", "password": "WrongPass999"},
        )

    assert resp.status_code == 401
    assert resp.json()["errorCode"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_admin_login_rejects_bootstrap_admin():
    """Bootstrap admins are setup-only — the token API must not mint for them."""
    await _seed_bootstrap_admin("bootadmin", "BootPass12345")

    async with _client() as client:
        resp = await client.post(
            "/v1/admin/login",
            json={"username": "bootadmin", "password": "BootPass12345"},
        )

    assert resp.status_code == 401
    assert resp.json()["errorCode"] == "INVALID_CREDENTIALS"
