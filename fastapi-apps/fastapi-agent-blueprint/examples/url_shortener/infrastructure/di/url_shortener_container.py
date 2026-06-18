from dependency_injector import containers, providers

from ...domain.services.link_service import LinkService
from ..repositories.link_repository import LinkRepository


class UrlShortenerContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    link_repository = providers.Singleton(
        LinkRepository,
        database=core_container.database,
    )

    link_service = providers.Factory(
        LinkService,
        link_repository=link_repository,
    )
