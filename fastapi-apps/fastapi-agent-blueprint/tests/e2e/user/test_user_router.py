import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from src._apps.server.app import app
from src._apps.server.testing import (
    override_current_user,
    reset_current_user_override,
)
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN, USER_ROLE_USER
from src.user.infrastructure.database.models.user_model import UserModel
from tests.factories.user_factory import make_user_dto


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


@pytest_asyncio.fixture
async def admin_override():
    """Force ``get_current_user`` to return a non-bootstrap admin for the test.

    The existing CUD behaviour tests are now admin-gated; this override lets
    them keep asserting business logic without minting a real admin token. It
    is always reset on teardown so it cannot leak into other tests.
    """
    override_current_user(app, make_user_dto(role=USER_ROLE_ADMIN))
    try:
        yield
    finally:
        reset_current_user_override(app)


async def _promote_to_admin(test_db, user_id: int) -> None:
    async with test_db.session() as session:
        await session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(role=USER_ROLE_ADMIN)
        )
        await session.commit()


async def _role_of(test_db, user_id: int) -> str:
    async with test_db.session() as session:
        model = await session.get(UserModel, user_id)
        return model.role


async def _register(client: AsyncClient, suffix: str) -> dict:
    response = await client.post(
        "/v1/auth/register",
        json={
            "username": f"e2eauth{suffix}",
            "fullName": "E2E Auth User",
            "email": f"e2eauth{suffix}@example.com",
            "password": "secret",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _auth_headers(token_data: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_data['accessToken']}"}


@pytest.mark.asyncio
async def test_user_routes_require_authentication():
    async with _client() as client:
        response = await client.get("/v1/users")

    assert response.status_code == 401
    assert response.json()["errorCode"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_user_with_token(admin_override):
    async with _client() as client:
        token_data = await _register(client, "createowner")
        response = await client.post(
            "/v1/user",
            headers=_auth_headers(token_data),
            json={
                "username": "e2euser",
                "fullName": "E2E User",
                "email": "e2e@example.com",
                "password": "secret",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "e2euser"
    assert "password" not in data["data"]
    assert "role" not in data["data"]


@pytest.mark.asyncio
async def test_admin_can_read_users(admin_override):
    async with _client() as client:
        created = await client.post(
            "/v1/user",
            json={
                "username": "readtarget",
                "fullName": "Read Target",
                "email": "readtarget@example.com",
                "password": "secret",
            },
        )
        user_id = created.json()["data"]["id"]
        listing = await client.get("/v1/users")
        single = await client.get(f"/v1/user/{user_id}")
        by_ids = await client.get(f"/v1/user/by-ids?ids={user_id}")

    assert listing.status_code == 200
    assert isinstance(listing.json()["data"], list)
    assert single.status_code == 200
    assert single.json()["data"]["id"] == user_id
    assert by_ids.status_code == 200
    assert [item["id"] for item in by_ids.json()["data"]] == [user_id]


@pytest.mark.asyncio
async def test_create_user_duplicate_returns_field_errors(admin_override):
    payload = {
        "username": "e2edup",
        "fullName": "E2E Duplicate",
        "email": "e2edup@example.com",
        "password": "secret",
    }

    async with _client() as client:
        token_data = await _register(client, "dupowner")
        headers = _auth_headers(token_data)
        first = await client.post("/v1/user", headers=headers, json=payload)
        second = await client.post("/v1/user", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    body = second.json()
    assert body["success"] is False
    assert body["errorCode"] == "USER_ALREADY_EXISTS"
    assert body["errorDetails"]["errors"] == [
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
async def test_create_users_duplicate_payload_is_all_or_nothing(admin_override):
    payload = [
        {
            "username": "e2ebatchdup",
            "fullName": "E2E Batch One",
            "email": "e2ebatch-one@example.com",
            "password": "secret",
        },
        {
            "username": "e2ebatchdup",
            "fullName": "E2E Batch Two",
            "email": "e2ebatch-two@example.com",
            "password": "secret",
        },
    ]

    async with _client() as client:
        token_data = await _register(client, "batchowner")
        headers = _auth_headers(token_data)
        response = await client.post("/v1/users", headers=headers, json=payload)
        list_response = await client.get("/v1/users?pageSize=100", headers=headers)

    assert response.status_code == 422
    body = response.json()
    assert body["errorCode"] == "BUSINESS_VALIDATION_ERROR"
    assert body["errorDetails"]["errors"] == [
        {
            "field": "username",
            "message": "Duplicate username in request payload",
            "type": "duplicate",
        }
    ]
    usernames = {item["username"] for item in list_response.json()["data"]}
    assert "e2ebatchdup" not in usernames


@pytest.mark.asyncio
async def test_update_user_allows_own_email_and_rejects_another_users_email(
    admin_override,
):
    first_payload = {
        "username": "e2eupdateone",
        "fullName": "E2E Update One",
        "email": "e2eupdateone@example.com",
        "password": "secret",
    }
    second_payload = {
        "username": "e2eupdatetwo",
        "fullName": "E2E Update Two",
        "email": "e2eupdatetwo@example.com",
        "password": "secret",
    }

    async with _client() as client:
        token_data = await _register(client, "updateowner")
        headers = _auth_headers(token_data)
        first = await client.post("/v1/user", headers=headers, json=first_payload)
        second = await client.post("/v1/user", headers=headers, json=second_payload)
        first_id = first.json()["data"]["id"]
        second_id = second.json()["data"]["id"]

        own_email = await client.put(
            f"/v1/user/{first_id}",
            headers=headers,
            json={"email": first_payload["email"]},
        )
        conflicting_email = await client.put(
            f"/v1/user/{second_id}",
            headers=headers,
            json={"email": first_payload["email"]},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert own_email.status_code == 200
    assert conflicting_email.status_code == 409
    assert conflicting_email.json()["errorDetails"]["errors"] == [
        {
            "field": "email",
            "message": "email already exists",
            "type": "unique",
        }
    ]


# RBAC (#199) ===============================================================


@pytest.mark.asyncio
async def test_user_cud_is_forbidden_for_non_admin():
    """A real (role=user) token reaches require_admin and is rejected with 403."""
    user_payload = {
        "username": "rbacnew",
        "fullName": "RBAC New",
        "email": "rbacnew@example.com",
        "password": "secret",
    }

    async with _client() as client:
        token_data = await _register(client, "rbacuser")
        headers = _auth_headers(token_data)

        create = await client.post("/v1/user", headers=headers, json=user_payload)
        batch = await client.post("/v1/users", headers=headers, json=[user_payload])
        update_one = await client.put(
            "/v1/user/1", headers=headers, json={"fullName": "x"}
        )
        delete_one = await client.delete("/v1/user/1", headers=headers)

    for response in (create, batch, update_one, delete_one):
        assert response.status_code == 403, response.text
        assert response.json()["errorCode"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_user_reads_are_forbidden_for_non_admin():
    """User reads expose other users' PII, so they are admin-only too (#199)."""
    async with _client() as client:
        token_data = await _register(client, "rbacreader")
        headers = _auth_headers(token_data)

        listing = await client.get("/v1/users", headers=headers)
        single = await client.get("/v1/user/1", headers=headers)
        by_ids = await client.get("/v1/user/by-ids?ids=1", headers=headers)

    for response in (listing, single, by_ids):
        assert response.status_code == 403, response.text
        assert response.json()["errorCode"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_create_user_with_real_token(test_db):
    """A real token whose DB role is admin passes the gate (full auth chain)."""
    async with _client() as client:
        token_data = await _register(client, "rbacadmin")
        await _promote_to_admin(test_db, token_data["user"]["id"])

        response = await client.post(
            "/v1/user",
            headers=_auth_headers(token_data),
            json={
                "username": "rbacadmincreated",
                "fullName": "RBAC Admin Created",
                "email": "rbacadmincreated@example.com",
                "password": "secret",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["username"] == "rbacadmincreated"


@pytest.mark.asyncio
async def test_bootstrap_admin_is_forbidden():
    """Bootstrap admins are setup-only and must not pass the API admin gate."""
    override_current_user(
        app, make_user_dto(role=USER_ROLE_ADMIN, is_bootstrap_admin=True)
    )
    try:
        async with _client() as client:
            create = await client.post(
                "/v1/user",
                json={
                    "username": "bootstrapblocked",
                    "fullName": "Bootstrap Blocked",
                    "email": "bootstrapblocked@example.com",
                    "password": "secret",
                },
            )
            read = await client.get("/v1/users")
    finally:
        reset_current_user_override(app)

    for response in (create, read):
        assert response.status_code == 403, response.text
        assert response.json()["errorCode"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_user_ignores_role_escalation(admin_override, test_db):
    """role/permissions in the PUT body are silently ignored (no self-escalation)."""
    async with _client() as client:
        created = await client.post(
            "/v1/user",
            json={
                "username": "noescalation",
                "fullName": "No Escalation",
                "email": "noescalation@example.com",
                "password": "secret",
            },
        )
        user_id = created.json()["data"]["id"]
        updated = await client.put(
            f"/v1/user/{user_id}",
            json={
                "fullName": "No Escalation Updated",
                "role": "admin",
                "permissions": ["accounts"],
            },
        )

    assert created.status_code == 200, created.text
    assert updated.status_code == 200, updated.text
    assert await _role_of(test_db, user_id) == USER_ROLE_USER
