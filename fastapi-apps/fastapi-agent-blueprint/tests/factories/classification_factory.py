from src.classification.domain.dtos.classification_dto import ClassificationDTO
from src.classification.interface.server.schemas.classification_schema import (
    ClassifyRequest,
)


def make_classification_dto(
    category: str = "positive",
    confidence: float = 0.95,
    reasoning: str = "The text expresses positive sentiment.",
) -> ClassificationDTO:
    return ClassificationDTO(
        category=category,
        confidence=confidence,
        reasoning=reasoning,
    )


def make_classify_request(
    text: str = "This is great!",
    categories: list[str] | None = None,
) -> ClassifyRequest:
    return ClassifyRequest(
        text=text,
        categories=categories,
    )
