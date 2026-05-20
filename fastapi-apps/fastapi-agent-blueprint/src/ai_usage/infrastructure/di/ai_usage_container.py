from dependency_injector import containers, providers

from src.ai_usage.domain.services.ai_usage_service import AiUsageService
from src.ai_usage.infrastructure.repositories.ai_usage_repository import (
    AiUsageRepository,
)


class AiUsageContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    ai_usage_repository = providers.Singleton(
        AiUsageRepository,
        database=core_container.database,
    )

    ai_usage_service = providers.Factory(
        AiUsageService,
        ai_usage_repository=ai_usage_repository,
    )
