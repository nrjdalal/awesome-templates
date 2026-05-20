"""Unit tests for BaseS3VectorStore using a mock S3 Vectors client.

This test file also serves as the usage reference for implementing
S3 vector stores in domains (no example domain created).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.domain.value_objects.vector_search_result import VectorSearchResult
from src._core.infrastructure.vectors.s3.base_store import (
    BaseS3VectorStore,
)
from src._core.infrastructure.vectors.vector_model import (
    VectorData,
    VectorModel,
    VectorModelMeta,
)

# -- Test fixtures (domain implementation reference) -------------------


class DocVectorModel(VectorModel):
    """Sample VectorModel -- define like this in domains."""

    __vector_meta__: ClassVar[VectorModelMeta] = VectorModelMeta(
        index_name="test-docs",
        dimension=4,
        distance_metric="cosine",
        filter_fields=["category"],
        non_filter_fields=["content"],
    )

    category: str
    content: str


class PutDocDTO(BaseModel):
    """Sample PutDTO -- passed to upsert."""

    key: str
    vector: list[float]
    category: str
    content: str


class DocResultDTO(BaseModel):
    """Sample ReturnDTO -- returned by search/get."""

    category: str
    content: str


# -- Fake S3 Vectors Client --------------------------------------------


class FakeS3VectorsClient:
    """In-memory S3 Vectors client mock."""

    def __init__(self) -> None:
        self._indexes: dict[str, list[dict[str, Any]]] = {}

    async def put_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        vectors: list[dict[str, Any]],
        **kw: Any,
    ) -> dict[str, Any]:
        key = vectorBucketName + "/" + indexName
        self._indexes.setdefault(key, [])
        for v in vectors:
            self._indexes[key] = [
                existing
                for existing in self._indexes[key]
                if existing["key"] != v["key"]
            ]
            self._indexes[key].append(v)
        return {}

    async def query_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        topK: int,
        queryVector: dict[str, Any],
        returnMetadata: bool = False,
        returnDistance: bool = False,
        filter: dict[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        key = vectorBucketName + "/" + indexName
        items = list(self._indexes.get(key, []))

        if filter:
            items = [
                item
                for item in items
                if all(item.get("metadata", {}).get(k) == v for k, v in filter.items())
            ]

        results = []
        for i, item in enumerate(items[:topK]):
            entry: dict[str, Any] = {"key": item["key"]}
            if returnMetadata:
                entry["metadata"] = item.get("metadata", {})
            if returnDistance:
                entry["distance"] = 0.1 * (i + 1)
            results.append(entry)

        return {"vectors": results}

    async def get_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        keys: list[str],
        returnMetadata: bool = False,
        **kw: Any,
    ) -> dict[str, Any]:
        idx_key = vectorBucketName + "/" + indexName
        items = self._indexes.get(idx_key, [])
        key_set = set(keys)

        results = []
        for item in items:
            if item["key"] in key_set:
                entry: dict[str, Any] = {"key": item["key"]}
                if returnMetadata:
                    entry["metadata"] = item.get("metadata", {})
                results.append(entry)

        return {"vectors": results}

    async def delete_vectors(
        self,
        *,
        vectorBucketName: str,
        indexName: str,
        keys: list[str],
        **kw: Any,
    ) -> dict[str, Any]:
        idx_key = vectorBucketName + "/" + indexName
        key_set = set(keys)
        if idx_key in self._indexes:
            self._indexes[idx_key] = [
                item for item in self._indexes[idx_key] if item["key"] not in key_set
            ]
        return {}


class FakeS3VectorClient:
    def __init__(self) -> None:
        self._client = FakeS3VectorsClient()

    @asynccontextmanager
    async def client(self):  # noqa: ANN201
        yield self._client


# -- Sample Store (domain implementation reference) --------------------


class DocS3VectorStore(BaseS3VectorStore[DocResultDTO]):
    """Sample Store -- implement like this in domains."""

    def __init__(self, s3vector_client: FakeS3VectorClient) -> None:
        super().__init__(
            s3vector_client=s3vector_client,
            model=DocVectorModel,
            return_entity=DocResultDTO,
            bucket_name="test-bucket",
        )

    def _to_model(self, entity: BaseModel) -> VectorModel:
        data = entity.model_dump()
        return DocVectorModel(
            key=data["key"],
            data=VectorData(float32=data["vector"]),
            category=data["category"],
            content=data["content"],
        )


@pytest.fixture
def store() -> DocS3VectorStore:
    return DocS3VectorStore(s3vector_client=FakeS3VectorClient())


# -- Tests -------------------------------------------------------------


class TestUpsertAndGet:
    @pytest.mark.asyncio
    async def test_upsert_and_get(self, store: DocS3VectorStore) -> None:
        entities = [
            PutDocDTO(
                key="v1",
                vector=[0.1, 0.2, 0.3, 0.4],
                category="tech",
                content="Hello",
            ),
        ]
        count = await store.upsert(entities=entities)
        assert count == 1

        results = await store.get(keys=["v1"])
        assert len(results) == 1
        assert results[0].category == "tech"
        assert results[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_upsert_overwrites_same_key(self, store: DocS3VectorStore) -> None:
        await store.upsert(
            entities=[
                PutDocDTO(
                    key="v1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="tech",
                    content="Old",
                ),
            ]
        )
        await store.upsert(
            entities=[
                PutDocDTO(
                    key="v1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="tech",
                    content="New",
                ),
            ]
        )

        results = await store.get(keys=["v1"])
        assert len(results) == 1
        assert results[0].content == "New"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_result(self, store: DocS3VectorStore) -> None:
        for i in range(3):
            await store.upsert(
                entities=[
                    PutDocDTO(
                        key="v" + str(i),
                        vector=[0.1, 0.2, 0.3, 0.4],
                        category="tech",
                        content="Doc " + str(i),
                    ),
                ]
            )

        result = await store.search(
            query=VectorQuery(vector=[0.1, 0.2, 0.3, 0.4], top_k=10)
        )

        assert isinstance(result, VectorSearchResult)
        assert result.count == 3
        assert len(result.items) == 3
        assert result.distances is not None
        assert len(result.distances) == 3

    @pytest.mark.asyncio
    async def test_search_with_filter(self, store: DocS3VectorStore) -> None:
        await store.upsert(
            entities=[
                PutDocDTO(
                    key="v1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="tech",
                    content="Tech",
                ),
                PutDocDTO(
                    key="v2",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="art",
                    content="Art",
                ),
            ]
        )

        result = await store.search(
            query=VectorQuery(
                vector=[0.1, 0.2, 0.3, 0.4],
                top_k=10,
                filters={"category": "tech"},
            )
        )

        assert result.count == 1
        assert result.items[0].category == "tech"

    @pytest.mark.asyncio
    async def test_search_top_k_limit(self, store: DocS3VectorStore) -> None:
        for i in range(5):
            await store.upsert(
                entities=[
                    PutDocDTO(
                        key="v" + str(i),
                        vector=[0.1, 0.2, 0.3, 0.4],
                        category="tech",
                        content="Doc " + str(i),
                    ),
                ]
            )

        result = await store.search(
            query=VectorQuery(vector=[0.1, 0.2, 0.3, 0.4], top_k=2)
        )
        assert result.count == 2

    @pytest.mark.asyncio
    async def test_search_without_distance(self, store: DocS3VectorStore) -> None:
        await store.upsert(
            entities=[
                PutDocDTO(
                    key="v1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="tech",
                    content="Doc",
                ),
            ]
        )

        result = await store.search(
            query=VectorQuery(
                vector=[0.1, 0.2, 0.3, 0.4],
                top_k=10,
                return_distance=False,
            )
        )
        assert result.distances is None


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete(self, store: DocS3VectorStore) -> None:
        await store.upsert(
            entities=[
                PutDocDTO(
                    key="v1",
                    vector=[0.1, 0.2, 0.3, 0.4],
                    category="tech",
                    content="Doc",
                ),
            ]
        )

        result = await store.delete(keys=["v1"])
        assert result is True

        results = await store.get(keys=["v1"])
        assert len(results) == 0


class TestBatch:
    @pytest.mark.asyncio
    async def test_upsert_batch_handles_large_input(
        self, store: DocS3VectorStore
    ) -> None:
        """501 vectors should be split into 2 API calls (500 + 1)."""
        entities = [
            PutDocDTO(
                key="v" + str(i),
                vector=[0.1, 0.2, 0.3, 0.4],
                category="tech",
                content="Doc " + str(i),
            )
            for i in range(501)
        ]
        count = await store.upsert(entities=entities)
        assert count == 501

        sample = await store.get(keys=["v0", "v250", "v500"])
        assert len(sample) == 3
