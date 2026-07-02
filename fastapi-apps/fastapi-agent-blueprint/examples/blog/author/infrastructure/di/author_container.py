from dependency_injector import containers, providers

from ...domain.services.author_service import AuthorService
from ..repositories.author_repository import (
    AuthorRepository,
)


class AuthorContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()
    author_repository = providers.Singleton(
        AuthorRepository,
        database=core_container.database,
    )
    author_service = providers.Factory(
        AuthorService,
        author_repository=author_repository,
    )
