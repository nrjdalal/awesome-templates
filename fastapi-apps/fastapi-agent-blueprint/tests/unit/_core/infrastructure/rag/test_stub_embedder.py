from __future__ import annotations

import math

import pytest

from src._core.infrastructure.rag.stub_embedder import StubEmbedder


@pytest.mark.asyncio
async def test_returns_128_dim_vector():
    embedder = StubEmbedder()
    vector = await embedder.embed_text("hello world")

    assert len(vector) == 128


@pytest.mark.asyncio
async def test_is_deterministic():
    embedder = StubEmbedder()

    v1 = await embedder.embed_text("consistent text")
    v2 = await embedder.embed_text("consistent text")

    assert v1 == v2


@pytest.mark.asyncio
async def test_different_inputs_produce_different_vectors():
    embedder = StubEmbedder()

    v1 = await embedder.embed_text("alpha beta")
    v2 = await embedder.embed_text("gamma delta")

    assert v1 != v2


@pytest.mark.asyncio
async def test_embed_batch_matches_embed_text():
    embedder = StubEmbedder()
    texts = ["first phrase", "second phrase"]

    batch = await embedder.embed_batch(texts)
    individual = [await embedder.embed_text(t) for t in texts]

    assert batch == individual


@pytest.mark.asyncio
async def test_vectors_are_l2_normalised():
    embedder = StubEmbedder()

    vector = await embedder.embed_text("some content with tokens")
    norm = math.sqrt(sum(x * x for x in vector))

    assert norm == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_empty_input_returns_zero_vector():
    embedder = StubEmbedder()

    vector = await embedder.embed_text("")

    assert len(vector) == 128
    assert all(x == 0.0 for x in vector)


def test_dimension_property_is_128():
    embedder = StubEmbedder()
    assert embedder.dimension == 128


def test_custom_dimension():
    embedder = StubEmbedder(dimension=64)
    assert embedder.dimension == 64
