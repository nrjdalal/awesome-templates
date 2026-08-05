import importlib

import structlog
from taskiq import AsyncBroker

from src._apps.worker.broker import container
from src._apps.worker.di.container import create_worker_container

# Cross-cutting worker tasks that live outside ``src/{domain}/`` are not
# auto-discovered by ``_bootstrap_domains`` — import them explicitly here so
# the ``@broker.task`` decorator registers them with the broker before the
# worker starts pulling jobs (#206 audit retention cleanup).
from src._apps.worker.tasks import audit_cleanup_task as _audit_cleanup  # noqa: F401
from src._core.config import settings
from src._core.infrastructure.discovery import discover_domains
from src._core.infrastructure.logging.configure import configure_logging
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
)
from src._core.infrastructure.notification.taskiq_middleware import (
    TaskFailureNotificationMiddleware,
)
from src._core.infrastructure.observability.otel_bootstrap import (
    maybe_configure_otel,
)

_logger = structlog.stdlib.get_logger("src._apps.worker.bootstrap")


def bootstrap_app(app: AsyncBroker) -> None:
    _configure_logging_pipeline()
    maybe_configure_otel(settings, service_name="fastapi-agent-blueprint-worker")
    # ORDER IS LOAD-BEARING, and not for a stylistic reason. ``wire()`` adds a
    # ``__self__`` provider to the container it is called on. After that, handing
    # that container to a domain container's ``DependenciesContainer`` raises
    #
    #     AttributeError: 'DependenciesContainer' object has no attribute '__self__'
    #
    # because the override walks the overriding container's provider names and
    # looks each one up on the DependenciesContainer. Measured post-wire: all
    # three construction forms fail — ``providers.Container(cls,
    # core_container=cc)``, ``cls(core_container=cc)``, and ``cls()`` followed by
    # ``core_container.override(cc)``. Building the domain containers first works.
    #
    # This is why the cross-cutting wire moved off module scope: it used to run at
    # import, i.e. before any domain container could be built. That made
    # ``create_worker_container`` unreachable-by-exception, which stayed invisible
    # only because the call sat inside a startup event that never fired
    # (see bootstrap_task_domains). Pinned by
    # tests/unit/_apps/worker/test_task_bootstrap_order.py.
    bootstrap_task_domains(create_worker_container(core_container=container))
    container.wire(modules=[_audit_cleanup])
    install_task_middleware(app, error_notifier_provider=container.error_notifier)


# ---------------------------------------------------------------------------
# Private orchestration steps
# ---------------------------------------------------------------------------


def _configure_logging_pipeline() -> None:
    """Configure structlog before any task can run."""
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.effective_log_json,
    )


def install_task_middleware(app: AsyncBroker, *, error_notifier_provider) -> None:
    """Bind task context, log failures, retry transient errors, and alert (#310).

    Public because the server installs the same stack on the inline broker: under
    ``BROKER_TYPE=inmemory`` (the shipped default) ``.kiq()`` executes the task in
    the *server* process, and that process never imports ``worker/app.py`` — so
    without this call the inline broker ran tasks through an empty middleware
    list. No retry, no ``task_error`` record, no #310 alert, no correlation-id
    binding, and the absence of the error-logging middleware is itself what hid
    the failure (#324).

    ``error_notifier_provider`` is a parameter rather than the module-level
    ``container.error_notifier`` it used to close over, and callers must pass the
    provider from *their own* core tree. Passing the worker module's provider from
    the server gives that process two ``ErrorNotifier`` singletons: two
    ``NoopNotificationClient``s (so the disabled warning is logged twice, against
    the documented per-process invariant) and two independent cooldown dicts, so
    an HTTP-path alert would not suppress a duplicate task-path alert. Measured
    before this change: ``same ErrorNotifier: False / disabled warnings: 2``.

    Registration order is a behavioural contract, not a style choice. Taskiq
    runs ``on_error`` over ``reversed(broker.middlewares)``, and
    ``SmartRetryMiddleware`` re-kicks through an ``AsyncKicker`` that holds
    ``message.labels`` **by reference** — so its ``with_labels(_retries=...)``
    mutates the very dict the notifier reads. Registering
    ``TaskFailureNotificationMiddleware`` LAST makes its ``on_error`` run
    FIRST, before ``_retries`` is incremented. Move it any earlier and the
    final-attempt check silently reads an already-bumped counter, shifting
    every alert one attempt early. Pinned by
    ``tests/unit/_core/infrastructure/notification/test_task_failure_notification_middleware.py::TestMiddlewareOrderingContract``.

    The retry middleware is constructed once and shared: the notifier reads its
    retry defaults so the two cannot disagree about what "final attempt" means.
    (It reads only *immutable* config off that instance — per-attempt state lives
    in ``message.labels`` — so sharing is a config-drift guard, not a
    state-sharing requirement.)

    **Idempotent.** Called twice on one broker it rebinds the existing notifier's
    provider instead of appending a second stack. The server calls this on the
    module-level broker, and a process that bootstraps twice (test reloads, an
    ASGI reloader) would otherwise end up with eight middlewares — and, worse,
    with a notifier still holding the *first* container's ``error_notifier``
    provider, so alert cooldowns would key off a discarded container.
    """
    existing = next(
        (
            m
            for m in app.middlewares
            if isinstance(m, TaskFailureNotificationMiddleware)
        ),
        None,
    )
    if existing is not None:
        existing._error_notifier_provider = error_notifier_provider
        return

    retry_middleware = PermanentAwareSmartRetryMiddleware()
    app.add_middlewares(
        StructlogContextMiddleware(),
        retry_middleware,
        TaskErrorLoggingMiddleware(),
        TaskFailureNotificationMiddleware(
            error_notifier_provider=error_notifier_provider,
            retry_middleware=retry_middleware,
        ),
    )


def bootstrap_task_domains(container_with_domains) -> None:
    """Wire every domain's worker-task ``Provide`` markers. Call this directly.

    This replaced an ``@app.on_event("startup")`` registration that **never
    fired in any process**. ``AsyncBroker.on_event`` keys its handler dict by the
    argument it is given, and taskiq dispatches ``TaskiqEvents.WORKER_STARTUP``
    — an enum member that is not equal to the plain string ``"startup"``, since
    ``TaskiqEvents`` is not a ``str`` subclass. Verified after a full worker boot:

        broker.event_handlers keys -> ["'startup'"]      # nothing under the enum

    So the wiring never ran even on the real worker path, and the consequence was
    not the server-only gap #324 described. On the exact import the taskiq CLI
    performs (``src._apps.worker.app``), dispatching a domain task gave:

        AttributeError: 'Provide' object has no attribute 'ingest_existing_document'

    Calling it directly is also what lets the server reuse it: a FastAPI process
    never calls ``broker.startup()``, so no broker event can reach it. Nothing
    here needs a running loop or a ``TaskiqState`` — the body is ``.wire()`` calls
    only, which this module already performs at import time for the cross-cutting
    task.

    ``container_with_domains`` is anything exposing ``<domain>_container``
    attributes: the worker passes ``create_worker_container(...)``, the server
    passes its own ``app.state.container``. The server must NOT build a fresh
    worker container — ``providers.Container(DomainContainer, core_container=...)``
    overrides class-level state that the server has already overridden, and
    re-applying it raises ``AttributeError: 'DependenciesContainer' object has no
    attribute '__self__'``.
    """
    _bootstrap_domains(worker_container=container_with_domains)


def _bootstrap_domains(worker_container) -> None:
    """Dynamically bootstrap all domains detected by discover_domains().

    Domains without a worker bootstrap module are silently skipped so that
    server-only domains do not crash the worker boot.
    """
    for name in discover_domains():
        module_path = f"src.{name}.interface.worker.bootstrap.{name}_bootstrap"
        try:
            module = importlib.import_module(module_path)
            bootstrap_fn = getattr(module, f"bootstrap_{name}_domain")
        except (ModuleNotFoundError, AttributeError):
            _logger.debug("domain_worker_bootstrap_skipped", domain=name)
            continue

        domain_container = getattr(worker_container, f"{name}_container")
        bootstrap_fn(**{f"{name}_container": domain_container})
