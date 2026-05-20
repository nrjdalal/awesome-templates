from dependency_injector import containers, providers

from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.discovery import discover_domains, load_domain_container


def create_admin_container() -> containers.DynamicContainer:
    """Dynamically create the admin DI container.

    Same pattern as create_server_container() — auto-discovers all domains.
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
