from dependency_injector import containers, providers

from examples.blog.author.domain.services.author_service import AuthorService
from examples.blog.author.infrastructure.repositories.author_repository import (
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
