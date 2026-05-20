from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app as default_app
from src._apps.server.di.container import create_server_container
from src._apps.server.testing import override_database, reset_database_override
from src.ai_usage.interface.server.bootstrap.ai_usage_bootstrap import (
    create_ai_usage_container,
)
from src.ai_usage.interface.server.routers import ai_usage_router
from tests.factories.ai_usage_factory import make_create_ai_usage_request


@pytest.mark.asyncio
async def test_public_usage_api_is_disabled_by_default():
    async with AsyncClient(
        transport=ASGITransport(app=default_app), base_url="http://localhost"
    ) as client:
        response = await client.get("/v1/usage")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_enabled_usage_api_lists_summarizes_and_gets_detail(test_db):
    app = _build_usage_api_app(test_db)
    service = app.state.container.ai_usage_container().ai_usage_service()
    created = await service.record_usage_data(
        make_create_ai_usage_request(call_id="e2e-call")
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        list_response = await client.get("/v1/usage")
        summary_response = await client.get("/v1/usage/summary")
        detail_response = await client.get(f"/v1/usage/{created.id}")

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["callId"] == "e2e-call"
    assert summary_response.status_code == 200
    assert summary_response.json()["data"]["totalTokens"] >= 21
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == created.id


def _build_usage_api_app(test_db) -> FastAPI:
    app = FastAPI()
    container = create_server_container()
    app.state.container = container
    override_database(app, test_db)
    create_ai_usage_container(ai_usage_container=container.ai_usage_container)
    app.include_router(router=ai_usage_router.router, prefix="/v1", tags=["AI Usage"])
    app.add_event_handler("shutdown", lambda: reset_database_override(app))
    return app
