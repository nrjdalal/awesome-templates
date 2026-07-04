"""E2E: HTTP middleware contract (issue #2).

Covers the app-level middleware wired in ``src/_apps/server/bootstrap.py``:
CORS, X-Request-ID (asgi-correlation-id), and registration order. Regressions
here would silently break cross-origin requests, request tracing, or the
exception-handling/logging order the rest of the app depends on.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app
from src._core.config import settings


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


# --- CORS ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cors_preflight_returns_allow_origin(monkeypatch):
    monkeypatch.setattr(settings, "allow_origins", ["*"])
    async with _client() as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_cors_headers_on_simple_request(monkeypatch):
    monkeypatch.setattr(settings, "allow_origins", ["*"])
    async with _client() as client:
        response = await client.get("/health", headers={"Origin": "http://example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_reflects_origin_when_cookie_present(monkeypatch):
    monkeypatch.setattr(settings, "allow_origins", ["*"])
    async with _client() as client:
        response = await client.get(
            "/health",
            headers={"Origin": "http://example.com", "Cookie": "session=x"},
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://example.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


# --- X-Request-ID (asgi-correlation-id) ------------------------------------
@pytest.mark.asyncio
async def test_request_id_generated_when_absent():
    async with _client() as client:
        response = await client.get("/health")
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert uuid.UUID(request_id).version == 4


@pytest.mark.asyncio
async def test_request_id_echoed_when_valid_uuid():
    incoming = "0af7651916cd43dd8448eb211c80319c"
    async with _client() as client:
        response = await client.get("/health", headers={"X-Request-ID": incoming})
    assert response.headers.get("X-Request-ID") == incoming


# --- Registration order ----------------------------------------------------
def test_middleware_registration_order():
    from asgi_correlation_id import CorrelationIdMiddleware
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    from src._core.infrastructure.logging.request_log_middleware import (
        RequestLogMiddleware,
    )

    assert [m.cls for m in app.user_middleware] == [
        CorrelationIdMiddleware,
        RequestLogMiddleware,
        CORSMiddleware,
        TrustedHostMiddleware,
    ]


# --- TrustedHost -------------------------------------------------------------
@pytest.mark.asyncio
async def test_rejects_untrusted_host():
    async with _client() as client:
        response = await client.get("/health", headers={"Host": "evil.example.com"})
    assert response.status_code == 400
