from dependency_injector import containers, providers

from src.user.domain.services.user_service import UserService
from src.user.infrastructure.repositories.user_repository import UserRepository


class UserContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    user_repository = providers.Singleton(
        UserRepository,
        database=core_container.database,
    )

    user_service = providers.Factory(
        UserService,
        user_repository=user_repository,
    )
