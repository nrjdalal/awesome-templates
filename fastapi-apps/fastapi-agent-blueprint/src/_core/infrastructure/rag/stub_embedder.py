from __future__ import annotations

import hashlib
import logging
import math
import re

logger = logging.getLogger(__name__)

_DEFAULT_DIMENSION = 128
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class StubEmbedder:
    """Deterministic bag-of-words embedder used when no embedding provider
    is configured.

    Tokenises input on word boundaries, hashes each token into one of
    ``dimension`` buckets, and L2-normalises the resulting vector.
    Cosine distance between vectors therefore approximates shared-token
    overlap — useful enough for demos and tests, but *not* semantic.

    Warning is logged once at construction so ``make quickstart`` users
    are aware their retrieval path is keyword-based.
    """

    def __init__(self, dimension: int = _DEFAULT_DIMENSION) -> None:
        self._dimension = dimension
        logger.warning(
            "RAG stub embedder active — retrieval uses keyword bag-of-words, "
            "not semantic similarity. "
            "Set EMBEDDING_PROVIDER + EMBEDDING_MODEL for real embeddings."
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        return self._embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in _TOKEN_RE.findall(text.lower()):
            index = _bucket(token, self._dimension)
            vector[index] += 1.0
        return _l2_normalise(vector)


def _bucket(token: str, dimension: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension


def _l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return [x / norm for x in vector]
