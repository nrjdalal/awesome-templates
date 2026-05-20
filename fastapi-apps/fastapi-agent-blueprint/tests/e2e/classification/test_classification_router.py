import pytest
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app


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
