from __future__ import annotations

from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, Field

from src._core.common.uuid_utils import generate_vector_id


def _default_embedding_dimension() -> int:
    """Lazy-load settings to derive embedding dimension.

    Avoids module-level ``settings`` import so that test modules
    importing ``VectorModel`` do not trigger ``Settings()`` init.
    """
    from src._core.config import settings

    return settings.embedding_dimension


class VectorModelMeta(BaseModel):
    """S3 Vectors index schema metadata.

    ``DynamoModelMeta`` counterpart — declares index configuration
    that the migration CLI reads to create/compare indexes.

    ``dimension`` defaults to ``settings.embedding_dimension``
    (derived from ``EMBEDDING_PROVIDER`` + ``EMBEDDING_MODEL``).
    This ensures vector index dimension always matches the
    embedding model in use without manual synchronization.
    """

    index_name: str
    data_type: Literal["float32"] = "float32"
    dimension: int = Field(default_factory=_default_embedding_dimension)
    distance_metric: Literal["cosine", "euclidean"] = "cosine"
    filter_fields: list[str] = []
    non_filter_fields: list[str] = []


class VectorData(BaseModel):
    """S3 Vectors embedding data format."""

    float32: list[float]


class VectorModel(BaseModel):
    """Base class for S3 Vectors index models.

    ``DynamoModel`` counterpart — subclasses define index schema via
    ``__vector_meta__`` and declare metadata as Pydantic fields.

    Example::

        class DocumentVectorModel(VectorModel):
            __vector_meta__: ClassVar[VectorModelMeta] = VectorModelMeta(
                index_name="document-search",
                dimension=1536,
                distance_metric="cosine",
                filter_fields=["category", "author_id"],
                non_filter_fields=["content_preview"],
            )

            category: str
            author_id: str
            content_preview: str
    """

    __vector_meta__: ClassVar[VectorModelMeta]

    key: str = Field(default_factory=generate_vector_id)
    data: VectorData

    # ------------------------------------------------------------------
    # Serialization (model -> S3 Vectors API format)
    # ------------------------------------------------------------------

    def to_s3vector(self) -> dict[str, Any]:
        """Serialize to S3 Vectors ``put_vectors`` API format.

        ``DynamoModel.to_dynamodb()`` counterpart.
        All fields except ``key`` and ``data`` are extracted as metadata.
        """
        metadata = self.model_dump(exclude={"key", "data"}, exclude_none=True)
        return {
            "key": self.key,
            "data": self.data.model_dump(),
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Deserialization (S3 Vectors API response -> model)
    # ------------------------------------------------------------------

    @classmethod
    def from_s3vector(cls, raw: dict[str, Any]) -> Self:
        """Deserialize from S3 Vectors ``get_vectors``/``query_vectors`` response.

        ``DynamoModel.from_dynamodb()`` counterpart.
        """
        return cls(
            key=raw.get("key", ""),
            data=VectorData(**raw.get("data", {"float32": []})),
            **raw.get("metadata", {}),
        )
