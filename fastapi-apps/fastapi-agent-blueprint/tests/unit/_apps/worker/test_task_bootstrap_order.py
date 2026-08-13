"""The task runtime must be installed, and installed in the right order (#324).

Two defects sat behind one symptom.

**The startup event never fired, in any process.** `bootstrap_app` registered the
domain wiring with `@app.on_event("startup")`, but `AsyncBroker.on_event` keys its
handler dict by whatever it is given, and taskiq dispatches
`TaskiqEvents.WORKER_STARTUP` — an enum member that is not equal to the plain
string `"startup"`, because `TaskiqEvents` is not a `str` subclass. Measured after
a full worker boot at `d5c2a1d`:

    broker.event_handlers keys -> ["'startup'"]      # nothing under the enum

So `_bootstrap_domains` never ran even on the real worker path. On the exact
import the taskiq CLI performs, dispatching a domain task gave:

    AttributeError: 'Provide' object has no attribute 'ingest_existing_document'

The issue framed this as a server-only gap. It was not — the worker was equally
broken, and the blueprint's async ingestion had never worked.

**`wire()` poisons later domain-container construction.** `wire()` adds a
`__self__` provider to the container it is called on, and overriding a domain
container's `DependenciesContainer` with such a container then raises
`AttributeError: 'DependenciesContainer' object has no attribute '__self__'`.
Measured post-wire, all three construction forms fail:

    providers.Container(cls, core_container=cc)        -> AttributeError
    cls(core_container=cc)                             -> AttributeError
    cls(); dc.core_container.override(cc)              -> AttributeError

Building the domain containers *before* the wire works. This was invisible only
because the one call to `create_worker_container` sat inside the event that never
fired; making the call reachable surfaced it immediately.
"""

from __future__ import annotations

import pytest
from dependency_injector import containers, providers
from taskiq import InMemoryBroker
from taskiq.events import TaskiqEvents

from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.discovery import discover_domains, load_domain_container


class TestTheStartupEventKeyWasWrong:
    """Regression guards for the mechanism, not just the symptom. If someone
    reintroduces an `on_event("startup")` registration, these say why it is dead
    code rather than leaving the next reader to rediscover it."""

    def test_taskiq_events_is_not_a_str_enum(self):
        assert not issubclass(TaskiqEvents, str), (
            "if TaskiqEvents became a str enum, on_event('startup') might start "
            "matching and this whole finding would need rechecking"
        )
        assert TaskiqEvents.WORKER_STARTUP != "startup"

    def test_a_string_and_the_enum_are_different_handler_keys(self):
        broker = InMemoryBroker()

        # A raw string where taskiq wants `TaskiqEvents` — deliberately, since
        # this test asserts the two land in different handler buckets.
        @broker.on_event("startup")  # pyright: ignore[reportArgumentType]
        async def _by_string(state): ...

        @broker.on_event(TaskiqEvents.WORKER_STARTUP)
        async def _by_enum(state): ...

        assert "startup" in broker.event_handlers
        assert TaskiqEvents.WORKER_STARTUP in broker.event_handlers
        assert (
            broker.event_handlers["startup"]  # pyright: ignore[reportArgumentType]
            != broker.event_handlers[TaskiqEvents.WORKER_STARTUP]
        ), "the two registrations landed in the same bucket; recheck the fix"

    def test_bootstrap_no_longer_defers_domain_wiring_to_an_event(self):
        """Checked over the AST, not the source text.

        The first version of this test grepped for `on_event("startup")` and
        failed on the docstrings that *explain* the bug — prose is not code, and a
        text scan cannot tell them apart.
        """
        import ast
        import inspect

        from src._apps.worker import bootstrap

        tree = ast.parse(inspect.getsource(bootstrap))
        decorators = [
            ast.unparse(dec)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            for dec in node.decorator_list
        ]
        assert not [d for d in decorators if "on_event" in d], (
            f"domain wiring is back behind a broker event that taskiq never "
            f"dispatches; it must be called directly. Found: {decorators}"
        )
        assert hasattr(bootstrap, "bootstrap_task_domains")


class TestWireBeforeDomainContainersBreaksConstruction:
    """The ordering constraint `bootstrap_app` now encodes. Asserted on the DI
    library's real behaviour so the constraint is documented by a failing case
    rather than by a comment alone."""

    @pytest.fixture
    def audit_task_module(self):
        from src._apps.worker.tasks import audit_cleanup_task

        return audit_cleanup_task

    def _build_domain_container(self, core_container):
        holder = containers.DynamicContainer()
        holder.core_container = core_container
        cls = load_domain_container(discover_domains()[0])
        return providers.Container(cls, core_container=holder.core_container)

    def test_building_before_the_wire_succeeds(self, audit_task_module):
        core = CoreContainer()
        self._build_domain_container(core)  # must not raise
        core.wire(modules=[audit_task_module])

    def test_building_after_the_wire_raises(self, audit_task_module):
        core = CoreContainer()
        core.wire(modules=[audit_task_module])
        with pytest.raises(AttributeError, match="__self__"):
            self._build_domain_container(core)

    def test_wire_is_what_adds_the_self_provider(self, audit_task_module):
        """Names the mechanism, so a future DI upgrade that changes it fails here
        rather than silently making the ordering constraint unnecessary — or
        silently making it insufficient."""
        core = CoreContainer()
        assert "__self__" not in core.providers
        core.wire(modules=[audit_task_module])
        assert "__self__" in core.providers


class TestInstallTaskMiddlewareIsReusable:
    def test_it_takes_the_notifier_provider_from_the_caller(self):
        """The server must be able to pass its OWN tree's provider. Hardcoding the
        worker module's gave a server process two ErrorNotifiers, hence two
        NoopNotificationClients — two `notification_client_disabled` lines against
        the documented per-process invariant — and two independent cooldown dicts.
        """
        from src._apps.worker.bootstrap import install_task_middleware

        sentinel = object()
        broker = InMemoryBroker()
        install_task_middleware(broker, error_notifier_provider=sentinel)

        notifier = next(
            m
            for m in broker.middlewares
            if type(m).__name__ == "TaskFailureNotificationMiddleware"
        )
        # Private by design; the assertion is that bootstrap wired the provider
        # rather than a resolved notifier, which is only observable here.
        assert notifier._error_notifier_provider is sentinel  # pyright: ignore[reportAttributeAccessIssue]

    def test_the_only_load_bearing_inequality_is_retry_before_notifier(self):
        """taskiq runs `on_error` over `reversed(middlewares)`, so registered-last
        runs first. The notifier must run before the retry middleware bumps
        `_retries`, which means it must be registered after it.

        Deliberately asserting one inequality rather than the full chain: a
        cross-review order matrix showed the structlog and error-logging positions
        are behaviourally free, so pinning them over-specifies the contract and
        would fail a harmless reordering.
        """
        from src._apps.worker.bootstrap import install_task_middleware

        broker = InMemoryBroker()
        install_task_middleware(broker, error_notifier_provider=object())
        names = [type(m).__name__ for m in broker.middlewares]

        assert names.index("PermanentAwareSmartRetryMiddleware") < names.index(
            "TaskFailureNotificationMiddleware"
        )

    def test_installing_twice_rebinds_rather_than_appending(self):
        """Idempotent, and it rebinds the notifier's provider.

        The first version of this test asserted the opposite — that a second call
        appends — because the server guarded with `not broker.middlewares`. A
        post-merge review showed that guard was wrong in the way its own comment
        claimed it was right: it skipped installation but left the notifier
        holding the *first* container's `error_notifier`, so a second bootstrap
        re-wired the domain tasks to the new container while alert cooldowns kept
        keying off the discarded one. The guard is gone; the installer is
        idempotent instead.
        """
        from src._apps.worker.bootstrap import install_task_middleware
        from src._core.infrastructure.notification.taskiq_middleware import (
            TaskFailureNotificationMiddleware,
        )

        first_provider, second_provider = object(), object()
        broker = InMemoryBroker()

        install_task_middleware(broker, error_notifier_provider=first_provider)
        count = len(broker.middlewares)

        install_task_middleware(broker, error_notifier_provider=second_provider)
        assert len(broker.middlewares) == count, (
            "a second install appended a duplicate stack; the server calls this "
            "unconditionally, so a repeated bootstrap would double every hook"
        )

        notifier = next(
            m
            for m in broker.middlewares
            if isinstance(m, TaskFailureNotificationMiddleware)
        )
        assert notifier._error_notifier_provider is second_provider, (
            "the notifier kept the first container's provider, so alert cooldowns "
            "would key off a discarded container"
        )
