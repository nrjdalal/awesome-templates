"""E2E coverage for the `/docs` selector and OpenAPI handoff routes.

The selector page and `/openapi-download.json` route are dev-only. They support
the frontend handoff flow described in `docs/frontend-handoff.md`. Regressions
here would silently break the spec download button or expose the selector
outside dev — both surfaces other tooling depends on.
"""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


@pytest.mark.asyncio
async def test_docs_selector_returns_html():
    async with _client() as client:
        response = await client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    # Hero + recommended viewers + handoff link must be present on every load.
    assert "API Documentation" in body
    assert "Stoplight Elements" in body
    assert "Scalar API Reference" in body
    assert "Recommended" in body
    # The two viewer rows must carry the primary class so the accent strip
    # actually renders; secondary handoff/viewer rows must keep their class.
    assert "row primary" in body
    assert 'class="row"' in body
    # Light/dark theme system + toggle must be wired in.
    assert "data-theme" in body
    assert ':root[data-theme="dark"]' in body
    assert "prefers-color-scheme: dark" in body
    assert 'id="theme-toggle"' in body
    assert "aria-pressed" in body
    assert "localStorage" in body
    # AI-pattern clichés must stay out of the production surface.
    for cliche in (
        "linear-gradient",
        "-webkit-background-clip",
        "backdrop-filter",
    ):
        assert cliche not in body, f"AI-pattern cliche leaked: {cliche}"


@pytest.mark.asyncio
async def test_docs_selector_links_to_handoff_and_download():
    async with _client() as client:
        response = await client.get("/docs")
    body = response.text
    # The download row must point at the dedicated attachment route, not the
    # bare /openapi.json (which would render inline). Match the href tail to
    # stay agnostic to root_path prefixing.
    download_match = re.search(
        r'<a\s+class="row[^"]*"\s+href="([^"]*openapi-download\.json)"', body
    )
    assert download_match is not None, "download row href missing"
    assert download_match.group(1).endswith("/openapi-download.json")
    # Handoff guide link goes out to GitHub main; protect the path against
    # silent renames.
    assert "/docs/frontend-handoff.md" in body


@pytest.mark.asyncio
async def test_openapi_download_serves_attachment():
    async with _client() as client:
        response = await client.get("/openapi-download.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"].startswith("attachment")
    assert "openapi.json" in response.headers["content-disposition"]
    spec = response.json()
    assert "openapi" in spec
    assert "paths" in spec
    assert spec["paths"], "OpenAPI paths block must not be empty"


@pytest.mark.asyncio
async def test_openapi_download_matches_openapi_json():
    async with _client() as client:
        baseline = await client.get("/openapi.json")
        download = await client.get("/openapi-download.json")
    assert baseline.status_code == 200
    assert download.status_code == 200
    assert baseline.json() == download.json()


@pytest.mark.asyncio
async def test_legacy_theme_query_falls_through_to_default():
    """Old preview URLs (`/docs?theme=brutalist` etc.) are no longer routed
    to alternate renderers, but the dispatch was removed silently — FastAPI
    drops unknown query params, so the server must return the default
    selector unchanged. This test locks the graceful fallthrough so a future
    edit cannot accidentally re-introduce a stale renderer behind the same
    URL.
    """
    async with _client() as client:
        baseline = await client.get("/docs")
        legacy = await client.get("/docs?theme=brutalist")
    assert baseline.status_code == 200
    assert legacy.status_code == 200
    assert baseline.text == legacy.text


@pytest.mark.parametrize(
    "path",
    [
        "/docs-swagger",
        "/docs-redoc",
        "/docs-scalar",
        "/docs-elements",
        "/docs-rapidoc",
    ],
)
@pytest.mark.asyncio
async def test_docs_ui_routes_serve_html(path: str):
    """The selector links to five docs UI routes; verify each one is wired up
    and serves HTML (CDN renderers are loaded client-side, so the response
    body is a small bootstrap page rather than the full spec render).
    """
    async with _client() as client:
        response = await client.get(path)
    assert response.status_code == 200, f"{path} did not return 200"
    assert "text/html" in response.headers["content-type"]
