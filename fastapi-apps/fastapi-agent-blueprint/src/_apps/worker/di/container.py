from dependency_injector import containers, providers

from src._core.infrastructure.discovery import discover_domains, load_domain_container


def create_worker_container(core_container) -> containers.DynamicContainer:
    """Dynamically create the worker DI container.

    Args:
        core_container: CoreContainer instance injected from outside.
            The worker shares the CoreContainer created in broker.py.
    """
    container = containers.DynamicContainer()
    container.core_container = core_container

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
