from dependency_injector import containers

from src._core.infrastructure.discovery import discover_domains


def create_admin_container(server_container) -> containers.DynamicContainer:
    """Create the admin DI container as a view over the server's own tree.

    Args:
        server_container: the server ``DynamicContainer`` from
            ``app.state.container``. The admin dashboard is mounted onto the
            server process (``ui.run_with``), so it shares that process's
            containers rather than building a second set.

    Why this is a view and not its own tree
    ---------------------------------------
    This function used to call ``providers.Container(CoreContainer)`` and rebuild
    every domain container. One process then held **two** of every
    ``CoreContainer`` Singleton: two async engines and two QueuePools (with
    ``database_pool_size``/``database_max_overflow`` unset, up to 2 x (5 + 10) =
    30 connections against a 15-connection budget), two ``HttpClient``s, and two
    ``ErrorNotifier`` cooldown dicts — making the "per-process" notification
    cooldown really per-tree. Every optional-infra disabled warning was emitted
    twice, including the ``notification_client_disabled`` line that
    ``test_noop_notification_client_disabled_warning_emitted_once`` pins to
    exactly one occurrence. And ``override_database`` reached only the server
    tree, so a test that swapped the database got ``/v1/*`` on the swapped one
    while ``/admin/*`` and every audit write stayed on the real ``DATABASE_*``.

    Injecting the core container the way ``create_worker_container`` does is not
    available here, and this is the part worth reading before changing it:
    ``providers.Container(DomainContainer, core_container=...)`` **overrides
    class-level state** on the domain container. By the time admin mounts, the
    server has already applied that override, and re-applying it with a
    core container that is already in use raises

        AttributeError: 'DependenciesContainer' object has no attribute '__self__'

    Only a *brand new* core tree is accepted as the second override — which is
    the very thing being removed. The worker pattern works because a worker
    process wires those classes exactly once. So admin reuses the server's
    domain container providers rather than constructing its own.

    ``discover_domains()`` still drives the loop: the attributes it sets are what
    ``_discover_and_register_pages`` reads, and NiceGUI page registration happens
    at bootstrap time. The values stay *providers*, never resolved services, so
    the ``page_config._service_provider`` indirection is preserved.
    """
    container = containers.DynamicContainer()
    container.core_container = server_container.core_container

    for domain in discover_domains():
        setattr(
            container,
            f"{domain}_container",
            getattr(server_container, f"{domain}_container"),
        )

    return container
