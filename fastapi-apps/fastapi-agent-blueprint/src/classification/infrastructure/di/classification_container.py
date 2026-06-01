from dependency_injector import containers, providers

from src._core.config import settings
from src.ai_usage.domain.services.ai_usage_service import AiUsageService
from src.ai_usage.infrastructure.repositories.ai_usage_repository import (
    AiUsageRepository,
)
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

    # Cross-domain usage recorder (#197 Phase 5). Wiring-only import of the
    # ai_usage implementation; the adapter depends on the Protocol.
    ai_usage_repository = providers.Singleton(
        AiUsageRepository,
        database=core_container.database,
    )
    ai_usage_recorder = providers.Singleton(
        AiUsageService,
        ai_usage_repository=ai_usage_repository,
    )

    classifier = providers.Selector(
        _classifier_selector,
        real=providers.Singleton(
            PydanticAIClassifier,
            llm_model=core_container.llm_model,
            guardrails_enabled=settings.guardrails_enabled,
            usage_recorder=ai_usage_recorder,
            model_name=settings.llm_model_name or "",
            provider=settings.llm_provider,
        ),
        stub=providers.Singleton(StubClassifier),
    )

    classification_service = providers.Factory(
        ClassificationService,
        classifier=classifier,
    )
