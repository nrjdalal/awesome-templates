import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src._core.domain.value_objects.embedding_config import EmbeddingConfig

_has_pydantic_ai = importlib.util.find_spec("pydantic_ai") is not None


class TestEmbeddingConfigValueObject:
    """EmbeddingConfig frozen dataclass tests."""

    def test_frozen_dataclass(self):
        config = EmbeddingConfig(
            model_name="openai:text-embedding-3-small",
            dimension=1536,
            api_key="sk-test",
        )
        assert config.model_name == "openai:text-embedding-3-small"
        assert config.dimension == 1536
        assert config.api_key == "sk-test"

        with pytest.raises(AttributeError):
            config.model_name = "changed"  # type: ignore[misc]

    def test_defaults(self):
        config = EmbeddingConfig(model_name="bedrock:amazon.titan-embed-text-v2:0")
        assert config.dimension == 1536
        assert config.api_key is None
        assert config.aws_access_key_id is None
        assert config.aws_secret_access_key is None
        assert config.aws_region is None

    def test_bedrock_credentials(self):
        config = EmbeddingConfig(
            model_name="bedrock:amazon.titan-embed-text-v2:0",
            dimension=1024,
            aws_access_key_id="AKIA...",
            aws_secret_access_key="secret",
            aws_region="us-west-2",
        )
        assert config.aws_access_key_id == "AKIA..."
        assert config.aws_region == "us-west-2"


class TestAdapterImportError:
    """pydantic-ai 미설치 시 ImportError 발생 확인."""

    def test_raises_import_error_without_pydantic_ai(self):
        if _has_pydantic_ai:
            pytest.skip("pydantic-ai is installed; cannot test ImportError path")

        from src._core.infrastructure.embedding.pydantic_ai_embedding_adapter import (
            PydanticAIEmbeddingAdapter,
        )

        with pytest.raises(ImportError, match="pydantic-ai is required"):
            PydanticAIEmbeddingAdapter(
                embedding_config=EmbeddingConfig(
                    model_name="openai:text-embedding-3-small"
                ),
            )


@pytest.mark.skipif(not _has_pydantic_ai, reason="pydantic-ai not installed")
class TestPydanticAIEmbeddingAdapter:
    """pydantic-ai 설치 시 어댑터 동작 테스트."""

    def _make_adapter(self, model_name: str = "test:model", **kwargs):
        """Create adapter with mocked Embedder to avoid real API calls."""
        from src._core.infrastructure.embedding.pydantic_ai_embedding_adapter import (
            PydanticAIEmbeddingAdapter,
        )

        config = EmbeddingConfig(model_name=model_name, dimension=1536, **kwargs)
        with patch("pydantic_ai.Embedder") as mock_embedder_cls:
            mock_embedder = MagicMock()
            mock_embedder_cls.return_value = mock_embedder
            adapter = PydanticAIEmbeddingAdapter(embedding_config=config)
            adapter._embedder = mock_embedder
        return adapter

    def test_dimension_property(self):
        adapter = self._make_adapter(model_name="test:model")
        assert adapter.dimension == 1536

    @pytest.mark.asyncio
    async def test_embed_text(self):
        adapter = self._make_adapter()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2, 0.3]]
        adapter._embedder.embed_query = AsyncMock(return_value=mock_result)

        result = await adapter.embed_text("hello")
        assert result == [0.1, 0.2, 0.3]
        adapter._embedder.embed_query.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_embed_batch_non_openai(self):
        adapter = self._make_adapter(model_name="bedrock:titan")
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1, 0.2], [0.3, 0.4]]
        adapter._embedder.embed_documents = AsyncMock(return_value=mock_result)

        result = await adapter.embed_batch(["a", "b"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]
        adapter._embedder.embed_documents.assert_called_once_with(["a", "b"])

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self):
        adapter = self._make_adapter()
        result = await adapter.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_error_mapping_authentication(self):
        from src._core.infrastructure.embedding.exceptions import (
            EmbeddingAuthenticationException,
        )

        adapter = self._make_adapter()
        adapter._embedder.embed_query = AsyncMock(
            side_effect=RuntimeError("Authentication failed")
        )

        with pytest.raises(EmbeddingAuthenticationException):
            await adapter.embed_text("test")

    @pytest.mark.asyncio
    async def test_error_mapping_rate_limit(self):
        from src._core.infrastructure.embedding.exceptions import (
            EmbeddingRateLimitException,
        )

        adapter = self._make_adapter()
        adapter._embedder.embed_query = AsyncMock(
            side_effect=RuntimeError("Rate limit exceeded")
        )

        with pytest.raises(EmbeddingRateLimitException):
            await adapter.embed_text("test")

    @pytest.mark.asyncio
    async def test_error_mapping_generic(self):
        from src._core.infrastructure.embedding.exceptions import (
            EmbeddingException,
        )

        adapter = self._make_adapter()
        adapter._embedder.embed_query = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )

        with pytest.raises(EmbeddingException):
            await adapter.embed_text("test")


@pytest.mark.skipif(not _has_pydantic_ai, reason="pydantic-ai not installed")
class TestOpenAIBatchSplitting:
    """OpenAI 프로바이더의 배치 분할 로직 테스트."""

    def _make_openai_adapter(self):
        from src._core.infrastructure.embedding.pydantic_ai_embedding_adapter import (
            PydanticAIEmbeddingAdapter,
        )

        config = EmbeddingConfig(
            model_name="openai:text-embedding-3-small",
            dimension=1536,
            api_key="test-key",
        )
        with patch("pydantic_ai.Embedder"):
            adapter = PydanticAIEmbeddingAdapter(embedding_config=config)
        return adapter

    def test_split_into_batches_small(self):
        adapter = self._make_openai_adapter()
        texts = ["hello", "world"]
        batches = adapter._split_into_batches(texts)
        assert len(batches) == 1
        assert batches[0] == ["hello", "world"]

    def test_split_into_batches_exceeds_count(self):
        adapter = self._make_openai_adapter()
        texts = ["x"] * 2500
        batches = adapter._split_into_batches(texts)
        assert len(batches) == 2
        assert len(batches[0]) == 2048
        assert len(batches[1]) == 452

    def test_split_into_batches_text_too_long(self):
        from src._core.infrastructure.embedding.exceptions import (
            EmbeddingInputTooLongException,
        )

        adapter = self._make_openai_adapter()
        long_text = "word " * 10000  # well over 8192 tokens

        with pytest.raises(EmbeddingInputTooLongException):
            adapter._split_into_batches([long_text])

    @pytest.mark.asyncio
    async def test_embed_batch_openai_uses_splitting(self):
        adapter = self._make_openai_adapter()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1]] * 3
        adapter._embedder.embed_documents = AsyncMock(return_value=mock_result)

        result = await adapter.embed_batch(["a", "b", "c"])
        assert len(result) == 3
        adapter._embedder.embed_documents.assert_called_once()
