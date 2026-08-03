"""A server with the admin extra must hold ONE CoreContainer tree (#326).

`create_admin_container` used to call `providers.Container(CoreContainer)` and
rebuild every domain container, so a process with the admin extra held two of
every `CoreContainer` Singleton. Probed at `d5c2a1d`:

    C) server tree db is test_db  : True
    D) admin  tree db is test_db  : False
    E) audit repo db is test_db   : False -> sqlite:///./quickstart.db
    F) admin user_repo db is test : False
    H) engines distinct           : True

The consequences were a test split-brain (`/v1/*` on the swapped database while
`/admin/*` and every audit write stayed on the real `DATABASE_*`), two async
engines and two QueuePools per process, and two `ErrorNotifier` cooldown dicts —
making the "per-process" notification cooldown really per-tree.

These tests are the boot-topology assertions the audit's cluster A harness was a
precondition for. They need the `admin` extra; without it the server never mounts
admin and there is no second tree to assert about.
"""

from __future__ import annotations

import pytest

pytest.importorskip(
    "nicegui", reason="admin topology is only observable with the admin extra"
)

from src._apps.server.testing import (  # noqa: E402
    override_database,
    reset_database_override,
)
from src._core.infrastructure.persistence.rdb.database import Database  # noqa: E402


@pytest.fixture
def app():
    from src._apps.server.app import app as server_app

    if not hasattr(server_app.state, "admin_container"):
        pytest.skip("admin was not mounted on this app")
    yield server_app
    reset_database_override(server_app)
    # Drop any repository built against this test's throwaway :memory: database,
    # so a later test in the same process does not inherit it.
    server_app.state.container.user_container.user_repository.reset()


@pytest.fixture
def swapped_db(app):
    core = app.state.container.core_container()
    db = Database(
        database_engine="sqlite",
        database_user="",
        database_password="",
        database_host="",
        database_port=0,
        database_name=":memory:",
        config=core.db_config(),
    )
    override_database(app, db)
    return db


class TestOneCoreContainerPerProcess:
    def test_admin_and_server_share_the_core_container(self, app):
        server_core = app.state.container.core_container()
        admin_core = app.state.admin_container.core_container()
        assert admin_core is server_core, (
            "admin built its own CoreContainer — two async engines, two "
            "QueuePools, and two ErrorNotifier cooldown dicts per process"
        )

    @pytest.mark.parametrize(
        "singleton",
        [
            "http_client",
            "broker",
            "taskiq_manager",
            "embedding_client",
            "notification_client",
            "error_notifier",
        ],
    )
    def test_every_core_singleton_is_shared(self, app, singleton):
        server_core = app.state.container.core_container()
        admin_core = app.state.admin_container.core_container()
        assert getattr(server_core, singleton)() is getattr(admin_core, singleton)()

    def test_domain_containers_stay_providers(self, app):
        """`page_config._service_provider` holds a provider, not a resolved
        service, and that indirection has to survive sharing the tree."""
        admin_container = app.state.admin_container
        provider = admin_container.admin_identity_container
        assert callable(provider), "the domain container was resolved, not aliased"
        assert provider is app.state.container.admin_identity_container


class TestDatabaseOverrideReachesTheAdminTree:
    def test_one_override_reaches_every_consumer(self, app, swapped_db):
        """One test rather than four, and the repository singletons are reset.

        `user_repository` is a `Singleton`, so once anything in the process has
        resolved it — the autouse `_override_app_database` in `tests/e2e` does —
        it keeps the `Database` it was built with. Without the reset this passed
        in isolation and failed in the full suite, for a reason that has nothing
        to do with container topology. Asserting under a single override with the
        cache cleared tests the property and drops the ordering artefact.
        """
        from src._core.infrastructure.admin.audit.logger import get_audit_repository

        app.state.container.user_container.user_repository.reset()

        assert app.state.admin_container.core_container.database() is swapped_db, (
            "the admin core tree did not see the override"
        )
        assert (
            app.state.admin_container.user_container.user_repository().database
            is swapped_db
        ), "an admin domain repository did not see the override"
        assert (
            app.state.container.user_container.user_repository().database is swapped_db
        ), "the server domain repository regressed"
        assert get_audit_repository()._database is swapped_db, (
            "the audit repository froze the pre-override Database; audit rows "
            "would go to the real DATABASE_* while /v1/* used the swapped one"
        )

    def test_the_two_trees_share_one_engine(self, app):
        server_core = app.state.container.core_container()
        admin_core = app.state.admin_container.core_container()
        assert server_core.database().engine is admin_core.database().engine


class TestAuditRepositoryResolvesTheDatabaseLazily:
    """`bootstrap_admin` resolved `core_container.database()` and froze the
    instance into module state via `configure_audit_repository`, so an override
    applied *after* bootstrap was invisible to every audit write and query."""

    def test_a_plain_database_still_works(self, app):
        """The worker cleanup task and the five existing unit-test call sites all
        pass a resolved `Database`. Accepting a provider must not break that."""
        from src._core.infrastructure.admin.audit.repository import (
            AdminAuditLogRepository,
        )

        core = app.state.container.core_container()
        database = Database(
            database_engine="sqlite",
            database_user="",
            database_password="",
            database_host="",
            database_port=0,
            database_name=":memory:",
            config=core.db_config(),
        )
        assert AdminAuditLogRepository(database)._database is database

    def test_a_provider_is_resolved_on_every_access(self):
        from src._core.infrastructure.admin.audit.repository import (
            AdminAuditLogRepository,
        )

        calls: list[int] = []
        first, second = object(), object()

        def provider():
            calls.append(1)
            return first if len(calls) == 1 else second

        repo = AdminAuditLogRepository(provider)  # type: ignore[arg-type]
        assert repo._database is first
        assert repo._database is second, (
            "the provider was cached, so a post-bootstrap override would not be "
            "picked up — the whole point of taking a provider"
        )
        assert len(calls) == 2
