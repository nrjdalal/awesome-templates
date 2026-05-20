from unittest.mock import AsyncMock, MagicMock

import pytest

from src._core.domain.value_objects.llm_config import LLMConfig
from src.classification.domain.dtos.classification_dto import ClassificationDTO
from src.classification.domain.services.classification_service import (
    ClassificationService,
)


class TestClassificationService:
    """ClassificationService delegates to ClassifierProtocol — uses mock only."""

    @pytest.mark.asyncio
    async def test_classify_returns_dto(self):
        expected = ClassificationDTO(
            category="positive", confidence=0.95, reasoning="Clear positive tone."
        )
        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=expected)

        service = ClassificationService(classifier=mock_classifier)
        result = await service.classify(
            text="This is great!", categories=["positive", "negative"]
        )

        assert result is expected
        mock_classifier.classify.assert_awaited_once_with(
            text="This is great!", categories=["positive", "negative"]
        )

    @pytest.mark.asyncio
    async def test_classify_without_categories(self):
        expected = ClassificationDTO(
            category="tech", confidence=0.8, reasoning="Technical topic."
        )
        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=expected)

        service = ClassificationService(classifier=mock_classifier)
        result = await service.classify(text="Python is a programming language")

        assert result is expected
        mock_classifier.classify.assert_awaited_once_with(
            text="Python is a programming language", categories=None
        )

    @pytest.mark.asyncio
    async def test_classify_propagates_exception(self):
        """Provider exceptions propagate to the server's generic_exception_handler."""
        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(side_effect=RuntimeError("API timeout"))

        service = ClassificationService(classifier=mock_classifier)

        with pytest.raises(RuntimeError, match="API timeout"):
            await service.classify(text="test input")


class TestLLMConfig:
    def test_frozen_dataclass(self):
        config = LLMConfig(model_name="openai:gpt-4o", api_key="sk-test")
        assert config.model_name == "openai:gpt-4o"
        assert config.api_key == "sk-test"

        with pytest.raises(AttributeError):
            config.model_name = "changed"  # type: ignore[misc]

    def test_api_key_defaults_to_none(self):
        config = LLMConfig(model_name="anthropic:claude-sonnet-4-20250514")
        assert config.api_key is None

    def test_bedrock_credentials(self):
        config = LLMConfig(
            model_name="bedrock:anthropic.claude-v2",
            aws_access_key_id="AKIA...",
            aws_secret_access_key="secret",
            aws_region="us-west-2",
        )
        assert config.aws_access_key_id == "AKIA..."
        assert config.aws_region == "us-west-2"
