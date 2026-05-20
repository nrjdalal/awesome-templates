from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel

from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.infrastructure.vectors.in_memory.base_store import (
    BaseInMemoryVectorStore,
)
from src._core.infrastructure.vectors.vector_model import (
    VectorData,
    VectorModel,
    VectorModelMeta,
)


class _FakeModel(VectorModel):
    __vector_meta__: ClassVar[VectorModelMeta] = VectorModelMeta(
        index_name="test-index",
        dimension=3,
        filter_fields=["category"],
        non_filter_fields=["label"],
    )

    category: str
    label: str


class _FakeDTO(BaseModel):
    key: str = ""
    category: str
    label: str


class _FakeStore(BaseInMemoryVectorStore[_FakeDTO]):
    def __init__(self) -> None:
        super().__init__(model=_FakeModel, return_entity=_FakeDTO)

    def _to_model(self, entity: BaseModel) -> VectorModel:
        # Test passes _FakeModel instances directly — return as-is
        assert isinstance(entity, _FakeModel)
        return entity


def _make_model(key: str, vector: list[float], category: str, label: str) -> _FakeModel:
    return _FakeModel(
        key=key,
        data=VectorData(float32=vector),
        category=category,
        label=label,
    )


@pytest.fixture
def store() -> _FakeStore:
    return _FakeStore()


@pytest.mark.asyncio
async def test_upsert_stores_vectors(store: _FakeStore):
    entities = [
        _make_model("k1", [1.0, 0.0, 0.0], "a", "one"),
        _make_model("k2", [0.0, 1.0, 0.0], "a", "two"),
    ]
    count = await store.upsert(entities)

    assert count == 2
    assert len(store._store) == 2
    record = store._store["k1"]
    assert record["vector"] == [1.0, 0.0, 0.0]
    assert record["metadata"]["category"] == "a"
    assert record["metadata"]["label"] == "one"


@pytest.mark.asyncio
async def test_search_returns_nearest_first(store: _FakeStore):
    await store.upsert(
        [
            _make_model("k1", [1.0, 0.0, 0.0], "a", "x-axis"),
            _make_model("k2", [0.0, 1.0, 0.0], "a", "y-axis"),
            _make_model("k3", [0.0, 0.0, 1.0], "a", "z-axis"),
        ]
    )

    result = await store.search(VectorQuery(vector=[1.0, 0.0, 0.0], top_k=3))

    assert len(result.items) == 3
    assert result.items[0].label == "x-axis"
    assert result.distances is not None
    assert result.distances[0] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.asyncio
async def test_search_respects_top_k(store: _FakeStore):
    await store.upsert(
        [_make_model(f"k{i}", [1.0, 0.0, 0.0], "a", f"l{i}") for i in range(5)]
    )

    result = await store.search(VectorQuery(vector=[1.0, 0.0, 0.0], top_k=2))

    assert len(result.items) == 2
    assert result.count == 2


@pytest.mark.asyncio
async def test_search_applies_eq_filter(store: _FakeStore):
    await store.upsert(
        [
            _make_model("k1", [1.0, 0.0, 0.0], "a", "one"),
            _make_model("k2", [0.0, 1.0, 0.0], "a", "two"),
            _make_model("k3", [0.0, 0.0, 1.0], "b", "three"),
        ]
    )

    result = await store.search(
        VectorQuery(
            vector=[1.0, 0.0, 0.0],
            top_k=10,
            filters={"category": {"$eq": "a"}},
        )
    )

    assert len(result.items) == 2
    for item in result.items:
        assert item.category == "a"


@pytest.mark.asyncio
async def test_search_applies_in_filter(store: _FakeStore):
    await store.upsert(
        [
            _make_model("k1", [1.0, 0.0, 0.0], "a", "one"),
            _make_model("k2", [0.0, 1.0, 0.0], "b", "two"),
            _make_model("k3", [0.0, 0.0, 1.0], "c", "three"),
        ]
    )

    result = await store.search(
        VectorQuery(
            vector=[1.0, 0.0, 0.0],
            top_k=10,
            filters={"category": {"$in": ["a", "b"]}},
        )
    )

    assert len(result.items) == 2
    categories = {item.category for item in result.items}
    assert categories == {"a", "b"}


@pytest.mark.asyncio
async def test_get_by_keys_returns_existing_only(store: _FakeStore):
    await store.upsert([_make_model("k1", [1.0, 0.0, 0.0], "a", "one")])

    results = await store.get(keys=["k1", "missing"])

    assert len(results) == 1
    assert results[0].label == "one"


@pytest.mark.asyncio
async def test_delete_removes_keys(store: _FakeStore):
    await store.upsert(
        [
            _make_model("k1", [1.0, 0.0, 0.0], "a", "one"),
            _make_model("k2", [0.0, 1.0, 0.0], "a", "two"),
        ]
    )

    deleted = await store.delete(keys=["k1"])
    assert deleted is True

    remaining = await store.get(keys=["k1", "k2"])
    assert len(remaining) == 1
    assert remaining[0].label == "two"
