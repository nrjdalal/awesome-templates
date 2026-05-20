from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseEmbeddingProtocol(Protocol):
    """Backend-agnostic embedding protocol.

    Abstraction boundary for embedding implementations.
    Both OpenAI and Bedrock Titan implement this protocol structurally.
    Domain services inject this protocol directly.

    ``dimension`` exposes the vector size so that callers
    (e.g. ``VectorModelMeta``) can align index configuration.
    """

    @property
    def dimension(self) -> int: ...

    async def embed_text(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
