from dependency_injector import containers, providers

from src._core.config import settings
from src.classification.domain.services.classification_service import (
    ClassificationService,
)
from src.classification.infrastructure.classifier.pydantic_ai_classifier import (
    PydanticAIClassifier,
)
from src.classification.infrastructure.classifier.stub_classifier import StubClassifier


def _classifier_selector() -> str:
    return "real" if settings.llm_model_name else "stub"


class ClassificationContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    classifier = providers.Selector(
        _classifier_selector,
        real=providers.Singleton(
            PydanticAIClassifier,
            llm_model=core_container.llm_model,
        ),
        stub=providers.Singleton(StubClassifier),
    )

    classification_service = providers.Factory(
        ClassificationService,
        classifier=classifier,
    )
