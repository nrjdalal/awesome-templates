from dependency_injector import containers, providers

from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.discovery import discover_domains, load_domain_container


def create_server_container() -> containers.DynamicContainer:
    """Dynamically create the server DI container.

    Auto-registers containers for all domains detected by discover_domains(),
    so this file does not need modification when adding a new domain.
    """
    container = containers.DynamicContainer()
    container.core_container = providers.Container(CoreContainer)

    for domain in discover_domains():
        domain_container_cls = load_domain_container(domain)
        setattr(
            container,
            f"{domain}_container",
            providers.Container(
                domain_container_cls, core_container=container.core_container
            ),
        )

    return container
