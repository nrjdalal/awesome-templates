import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app
from src._apps.server.testing import override_current_user, reset_current_user_override
from tests.factories.user_factory import make_user_dto


@pytest_asyncio.fixture(autouse=True)
async def _authenticated_user_override():
    """Bypass the JWT gate added in #197 Phase 1+2. /v1/classify now requires
    ``get_current_user`` at the router level — overriding it lets the
    validation-shape tests keep asserting 422 behaviour. The dedicated
    unauthenticated test resets the override locally to exercise the 401 path.
    """
    override_current_user(app, make_user_dto())
    try:
        yield
    finally:
        reset_current_user_override(app)


@pytest.mark.asyncio
async def test_classify_rejects_empty_text():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/classify",
            json={"text": "", "categories": ["a", "b"]},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_classify_rejects_missing_text():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/classify",
            json={"categories": ["a", "b"]},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_classify_route_registered_in_openapi():
    """Confirm route is wired without invoking the live LLM provider.

    Service-level happy-path is covered by the unit test with a mocked Agent.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})
    assert "/v1/classify" in paths
    assert "post" in paths["/v1/classify"]


# ── #197 Phase 1+2: auth gate on /v1/classify ───────────────────────────────


@pytest.mark.asyncio
async def test_classify_returns_401_without_bearer():
    reset_current_user_override(app)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            response = await client.post(
                "/v1/classify",
                json={"text": "hello", "categories": ["a", "b"]},
            )
    finally:
        override_current_user(app, make_user_dto())

    assert response.status_code == 401, response.text
    assert response.json()["errorCode"] == "UNAUTHORIZED"
