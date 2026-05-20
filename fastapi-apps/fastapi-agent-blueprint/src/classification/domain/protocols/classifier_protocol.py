from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.classification.domain.dtos.classification_dto import ClassificationDTO


@runtime_checkable
class ClassifierProtocol(Protocol):
    """Classifies text into categories and returns a structured result.

    Implementations live under ``src/classification/infrastructure/classifier/``.

    Bundled implementations:
    - ``PydanticAIClassifier`` — real LLM via PydanticAI Agent.
    - ``StubClassifier`` — deterministic fallback when no LLM is configured.
    """

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> ClassificationDTO: ...
