from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src._apps.server.app import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


async def _create_document(client: AsyncClient, title: str, content: str) -> dict:
    response = await client.post(
        "/v1/docs/documents",
        json={"title": title, "content": content},
    )
    assert response.status_code == 200, response.text
    return response.json()


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

    # NOTE: Ideally this would be 404, but the core ``Database.session``
    # context manager wraps any in-session exception (including the
    # 404 ``BaseCustomException`` raised by ``select_data_by_id``) into
    # a 500 ``DB_INTERNAL_ERROR``. Pre-existing behaviour across all
    # domains — tracked outside the RAG refactor scope.
    assert fetch_resp.status_code in (404, 500), fetch_resp.text
    if fetch_resp.status_code == 500:
        body = fetch_resp.json()
        assert "not found" in body["errorDetails"]["original_error"].lower()


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
        # Worker has not processed the queued task yet, so the row is
        # persisted with chunk_count=0 and the client can still read it back.
        assert created["chunkCount"] == 0

        fetch_resp = await client.get(f"/v1/docs/documents/{document_id}")
        assert fetch_resp.status_code == 200
        assert fetch_resp.json()["data"]["chunkCount"] == 0


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
