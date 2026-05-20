"""Classification graceful degradation with StubClassifier (#101 Part B + Phase 4).

When ``LLM_PROVIDER`` / ``LLM_MODEL`` are unset, ``ClassificationContainer``
resolves ``classifier`` to ``StubClassifier``. The stub must:

- not raise at construction time,
- produce a ``ClassificationDTO`` from ``.classify()`` calls,

so the domain survives ``make quickstart`` without real credentials.
"""

from __future__ import annotations

import importlib.util

import pytest

from src._core.config import settings

_has_pydantic_ai = importlib.util.find_spec("pydantic_ai") is not None


class TestClassificationStubFallback:
    @pytest.fixture
    def llm_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Force the LLM selector into its ``disabled`` branch."""
        monkeypatch.setattr(settings, "llm_provider", None)
        monkeypatch.setattr(settings, "llm_model", None)
        monkeypatch.setattr(settings, "llm_model_name", None)

    @pytest.mark.asyncio
    async def test_stub_classifier_produces_dto(self):
        from src.classification.domain.dtos.classification_dto import ClassificationDTO
        from src.classification.infrastructure.classifier.stub_classifier import (
            StubClassifier,
        )

        classifier = StubClassifier()
        result = await classifier.classify(
            text="This is a sample sentence.",
            categories=["positive", "negative"],
        )
        assert isinstance(result, ClassificationDTO)
        assert result.category == "positive"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_stub_classifier_returns_unknown_without_categories(self):
        from src.classification.infrastructure.classifier.stub_classifier import (
            StubClassifier,
        )

        classifier = StubClassifier()
        result = await classifier.classify(text="anything")
        assert result.category == "unknown"

    @pytest.mark.skipif(not _has_pydantic_ai, reason="pydantic-ai not installed")
    def test_core_container_llm_model_is_test_model(self, llm_disabled: None):
        from pydantic_ai.models.test import TestModel

        from src._core.infrastructure.di.core_container import CoreContainer

        container = CoreContainer()
        assert isinstance(container.llm_model(), TestModel)
