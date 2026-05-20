from __future__ import annotations

from typing import Any, Generic, TypeVar

from src._core.domain.dtos.rag import BaseChunkDTO, QueryAnswerDTO
from src._core.domain.protocols.answer_agent_protocol import AnswerAgentProtocol
from src._core.domain.protocols.embedding_protocol import BaseEmbeddingProtocol
from src._core.domain.protocols.vector_store_protocol import BaseVectorStoreProtocol
from src._core.domain.value_objects.vector_query import VectorQuery

TChunk = TypeVar("TChunk", bound=BaseChunkDTO)


class RagPipeline(Generic[TChunk]):
    """Reusable Retrieval-Augmented Generation pipeline.

    Domain-neutral orchestrator: embeds the question, runs a vector
    similarity search, hands the retrieved chunks to the answer agent.
    Consumer domains inject their own embedder, vector store (scoped to
    their chunk schema) and answer agent via DI.

    Returns ``(answer, retrieved_chunks)`` so the caller can surface
    retrieval metadata (counts, distances) without re-querying.
    """

    def __init__(
        self,
        embedder: BaseEmbeddingProtocol,
        vector_store: BaseVectorStoreProtocol[TChunk],
        answer_agent: AnswerAgentProtocol,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._answer_agent = answer_agent

    async def answer(
        self,
        question: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> tuple[QueryAnswerDTO, list[TChunk]]:
        vector = await self._embedder.embed_text(question)
        search_result = await self._vector_store.search(
            VectorQuery(vector=vector, top_k=top_k, filters=filters)
        )

        chunks = list(search_result.items)
        distances = search_result.distances or [None] * len(chunks)
        # Attach distance transiently so the answer agent can emit
        # citations without a second search round-trip. Underscore-
        # prefixed so it does not leak into serialisation.
        for chunk, distance in zip(chunks, distances, strict=False):
            chunk._distance = distance  # type: ignore[attr-defined]

        answer = await self._answer_agent.answer(
            question=question, context_chunks=chunks
        )
        return answer, chunks
