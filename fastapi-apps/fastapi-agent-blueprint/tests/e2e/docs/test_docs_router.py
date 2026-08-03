from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app
from src._apps.server.testing import override_current_user, reset_current_user_override
from tests.factories.user_factory import make_user_dto


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


@pytest_asyncio.fixture(autouse=True)
async def _authenticated_user_override():
    """Bypass the JWT gate added in #197 Phase 1+2 for existing business-logic
    tests. CUD + query routes now require ``get_current_user`` — overriding it
    with a fake non-admin user lets these tests keep asserting behaviour
    without minting a real Bearer. The dedicated unauthenticated test below
    resets the override locally to exercise the 401 path.
    """
    override_current_user(app, make_user_dto())
    try:
        yield
    finally:
        reset_current_user_override(app)


async def _create_document(client: AsyncClient, title: str, content: str) -> dict:
    response = await client.post(
        "/v1/docs/documents",
        json={"title": title, "content": content},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ── #197 Phase 1+2: auth gate on docs CUD + query ───────────────────────────


@pytest.mark.asyncio
async def test_docs_protected_routes_return_401_without_bearer():
    """Every /docs route requires a Bearer header. The GET reads are gated too
    because ``DocumentResponse`` returns the full raw ``content`` — public reads
    would let any unauthenticated caller enumerate and exfiltrate stored
    documents (Broken Access Control).
    """
    reset_current_user_override(app)
    try:
        async with _client() as client:
            create = await client.post(
                "/v1/docs/documents",
                json={"title": "x", "content": "y"},
            )
            delete = await client.delete("/v1/docs/documents/1")
            query = await client.post(
                "/v1/docs/query",
                json={"question": "x", "topK": 1},
            )
            list_docs = await client.get("/v1/docs/documents?pageSize=10")
            get_doc = await client.get("/v1/docs/documents/1")
    finally:
        override_current_user(app, make_user_dto())

    for resp in (create, delete, query, list_docs, get_doc):
        assert resp.status_code == 401, resp.text
        assert resp.json()["errorCode"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_create_document_and_fetch_by_id():
    async with _client() as client:
        created = await _create_document(client, "E2E Doc", "Some body content.")
        document_id = created["data"]["id"]

        response = await client.get(f"/v1/docs/documents/{document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["id"] == document_id
    assert body["data"]["title"] == "E2E Doc"
    assert body["data"]["chunkCount"] >= 1


@pytest.mark.asyncio
async def test_list_documents():
    async with _client() as client:
        for i in range(3):
            await _create_document(client, f"List Doc {i}", f"content-{i}")

        response = await client.get("/v1/docs/documents?pageSize=50")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 3


@pytest.mark.asyncio
async def test_delete_document():
    async with _client() as client:
        created = await _create_document(client, "Del Doc", "to-delete")
        document_id = created["data"]["id"]

        delete_resp = await client.delete(f"/v1/docs/documents/{document_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        fetch_resp = await client.get(f"/v1/docs/documents/{document_id}")

    # Deleted document → 404 not-found. The core ``Database.session`` context
    # manager now lets a domain ``BaseCustomException`` (the 404 raised by
    # ``select_data_by_id``) propagate instead of masking it as a 500 (#245).
    assert fetch_resp.status_code == 404, fetch_resp.text
    body = fetch_resp.json()
    assert "not found" in body["message"].lower()


@pytest.mark.asyncio
async def test_query_endpoint_returns_answer_with_citations():
    async with _client() as client:
        await _create_document(
            client, "Alpha Python", "Python is a popular programming language."
        )
        await _create_document(
            client,
            "Beta Rust",
            "Rust is a systems programming language focused on safety.",
        )

        response = await client.post(
            "/v1/docs/query",
            json={"question": "Tell me about Python", "topK": 5},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    data = body["data"]
    assert data["answer"]
    assert isinstance(data["citations"], list)
    assert data["retrievedCount"] >= 1
    cite = data["citations"][0]
    assert cite["sourceId"]
    assert cite["sourceTitle"]
    assert "excerpt" in cite


async def _drain_inline_tasks(timeout: float = 10.0) -> None:
    """Wait for the inline broker's detached tasks to finish.

    `InMemoryBroker` is constructed with `await_inplace=False`, so `.kiq()` only
    does `asyncio.create_task(...)` and returns. Anything asserting on a task's
    *effect* has to wait for those tasks rather than for a wall-clock interval.
    """
    import asyncio

    from src._apps.worker.broker import broker

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        running = [t for t in getattr(broker, "_running_tasks", set()) if not t.done()]
        if not running:
            return
        await asyncio.wait(
            running, timeout=deadline - asyncio.get_running_loop().time()
        )
    raise AssertionError(f"inline broker tasks did not finish within {timeout:.1f}s")


@pytest.mark.asyncio
async def test_create_large_document_defers_ingestion_to_worker():
    """Content beyond the sync threshold returns chunk_count=0 and leaves
    ingestion to ``ingest_document_task`` — the row still persists."""
    large_content = "Paragraph about async ingestion. " * 700  # > 20_000 chars
    assert len(large_content) > 20_000

    async with _client() as client:
        response = await client.post(
            "/v1/docs/documents",
            json={"title": "Large Doc", "content": large_content},
        )

        assert response.status_code == 200, response.text
        created = response.json()["data"]
        document_id = created["id"]
        # The response is returned before ingestion runs, so the row the caller
        # sees is still chunk_count=0. `.kiq()` is fire-and-forget on the inline
        # broker (await_inplace=False), so this is a property of the response, not
        # a race: the task cannot have run before `create_without_ingestion`
        # returned.
        assert created["chunkCount"] == 0

        # ...but on the inline broker the task then runs IN THIS PROCESS, so
        # ingestion does complete. Before #324 it could not: the task module's
        # `Provide` marker was never wired, so every dispatch died with
        # `AttributeError: 'Provide' object has no attribute
        # 'ingest_existing_document'` and the row stayed at chunk_count=0 forever
        # — invisible to /v1/docs/query, with no alert and no error record.
        # Draining rather than sleeping a fixed interval keeps this deterministic.
        await _drain_inline_tasks()

        fetch_resp = await client.get(f"/v1/docs/documents/{document_id}")
        assert fetch_resp.status_code == 200
        assert fetch_resp.json()["data"]["chunkCount"] > 0, (
            "async ingestion did not complete in-process; the inline broker is "
            "running the task without its domain DI wiring again (#324)"
        )


@pytest.mark.asyncio
async def test_query_respects_top_k():
    async with _client() as client:
        for i in range(3):
            await _create_document(
                client, f"TopK Doc {i}", f"unique content token{i} for ranking."
            )

        response = await client.post(
            "/v1/docs/query",
            json={"question": "token0", "topK": 1},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["retrievedCount"] == 1
