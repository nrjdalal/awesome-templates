"""RAG pipeline DTOs — domain-neutral data carriers.

These are read-result / transfer containers that flow through the RAG
pipeline (Embedder → VectorStore → AnswerAgent). They are NOT value
objects:

- They are not frozen — ``RagPipeline`` attaches a transient ``_distance``
  attribute on ``BaseChunkDTO`` before the answer agent sees them.
- They have no meaningful equality beyond Pydantic defaults.
- They cross layer boundaries (Repository → Service → Agent) as payloads.

VOs live under ``src/_core/domain/value_objects/`` (frozen, self-validating,
value-equal). DTOs live here.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field

_EXCERPT_LIMIT = 300


class BaseChunkDTO(BaseModel):
    """Generic retrievable chunk flowing through ``RagPipeline``.

    Consumer domains (e.g. ``src/docs/``) use this directly or extend it
    with extra metadata when they need richer filtering / citations.
    Fields are deliberately domain-neutral:

    - ``source_id`` — stringified identifier of the owning record so
      both integer-PK (RDB) and UUID-PK (DynamoDB) consumers plug in.
    - ``source_title`` — denormalised display title used by answer
      agents to build citations without re-reading the source record.
    """

    chunk_id: str = Field(default="", description="Vector store key for this chunk")
    content: str = Field(..., description="Chunk text content")
    chunk_index: int = Field(..., description="Ordinal position within the source")
    source_id: str = Field(..., description="Owning source identifier (stringified)")
    source_title: str = Field(
        ..., description="Owning source title (denormalised, for citations)"
    )


class CitationDTO(BaseModel):
    """Single citation in a RAG answer — domain-neutral."""

    source_id: str = Field(..., description="Owning source identifier")
    source_title: str = Field(..., description="Owning source title")
    excerpt: str = Field(..., description="Short excerpt of the chunk content")
    distance: float | None = Field(
        default=None, description="Vector distance (lower = closer)"
    )

    @classmethod
    def from_chunk(
        cls, chunk: BaseChunkDTO, excerpt_limit: int = _EXCERPT_LIMIT
    ) -> Self:
        """Build a citation from a retrieved chunk.

        ``RagPipeline`` attaches a transient ``_distance`` to each chunk
        before the answer agent runs, so both the stub and PydanticAI
        agents can call this factory without re-implementing the excerpt
        truncation / distance extraction logic.
        """
        text = (chunk.content or "").strip()
        if len(text) > excerpt_limit:
            text = text[:excerpt_limit].rstrip()
        distance = getattr(chunk, "_distance", None)
        return cls(
            source_id=chunk.source_id,
            source_title=chunk.source_title,
            excerpt=text,
            distance=distance if isinstance(distance, (int, float)) else None,
        )


class QueryAnswerDTO(BaseModel):
    """Structured answer produced by the RAG pipeline — domain-neutral."""

    answer: str = Field(..., description="Generated answer text")
    citations: list[CitationDTO] = Field(
        default_factory=list, description="Supporting citations"
    )
