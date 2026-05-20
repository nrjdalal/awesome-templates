from __future__ import annotations

import logging

from src.classification.domain.dtos.classification_dto import ClassificationDTO

logger = logging.getLogger(__name__)


class StubClassifier:
    """Deterministic classifier used when no LLM provider is configured.

    Returns the first provided category (or "unknown") so the classification
    pipeline still round-trips in ``make quickstart`` without external credentials.
    """

    def __init__(self) -> None:
        logger.warning(
            "Classification stub active — results are deterministic, not generated. "
            "Set LLM_PROVIDER + LLM_MODEL for real classification."
        )

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> ClassificationDTO:
        _ = text
        category = categories[0] if categories else "unknown"
        return ClassificationDTO(
            category=category,
            confidence=0.0,
            reasoning="Stub classifier — no LLM configured.",
        )
