from __future__ import annotations

from src.classification.domain.dtos.classification_dto import ClassificationDTO
from src.classification.domain.protocols.classifier_protocol import ClassifierProtocol


class ClassificationService:
    """Text classification service.

    Delegates all LLM interaction to the injected ``ClassifierProtocol``
    implementation. Provider SDK details (PydanticAI, stubs) live entirely
    in the infrastructure layer — this service knows nothing about them.
    """

    def __init__(self, classifier: ClassifierProtocol) -> None:
        self._classifier = classifier

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> ClassificationDTO:
        """Classify text into a category.

        Args:
            text: The text to classify.
            categories: Optional list of allowed categories.

        Returns:
            ClassificationDTO with category, confidence, and reasoning.
        """
        return await self._classifier.classify(text=text, categories=categories)
