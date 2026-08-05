import importlib

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from src._apps.server.di.container import create_server_container
from src._core.application.routers.api import docs_router, health_check_router
from src._core.config import settings
from src._core.exceptions.base_exception import BaseCustomException
from src._core.exceptions.exception_handlers import (
    custom_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# Register cross-cutting _core models on Base.metadata BEFORE
# _bootstrap_quickstart_schema_if_applicable() calls Base.metadata.create_all().
# The admin bootstrap also imports the audit package, but it may run after
# the quickstart create_all call — importing here is the durable hook.
from src._core.infrastructure.admin.audit import models as _audit_models  # noqa: F401
from src._core.infrastructure.discovery import discover_domains
from src._core.infrastructure.http.body_size_middleware import (
    BodySizeLimitMiddleware,
)
from src._core.infrastructure.logging.configure import configure_logging
from src._core.infrastructure.logging.request_log_middleware import (
    RequestLogMiddleware,
)
from src._core.infrastructure.observability.otel_bootstrap import (
    maybe_configure_otel,
)
from src._core.infrastructure.persistence.rdb.database import Base, Database

_logger = structlog.stdlib.get_logger("src._apps.server.bootstrap")


def bootstrap_app(app: FastAPI) -> None:
    _configure_logging_pipeline()
    maybe_configure_otel(settings, service_name="fastapi-agent-blueprint-server")
    _install_exception_handlers(app)
    _install_middleware(app)
    container = _setup_container(app)
    _bootstrap_quickstart_schema_if_applicable(container)
    _install_core_routes(app, container)
    _bootstrap_domains(app, container)
    _install_inline_task_runtime(container)
    _mount_admin_if_available(app)


# ---------------------------------------------------------------------------
# Private orchestration steps
# ---------------------------------------------------------------------------


def _configure_logging_pipeline() -> None:
    """Configure structlog before any route or middleware can emit records."""
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.effective_log_json,
    )


def _install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(BaseCustomException, custom_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


def _install_middleware(app: FastAPI) -> None:
    # Starlette applies the LAST one added as the OUTERMOST.
    # CorrelationIdMiddleware must see the raw request first (so it can read /
    # generate X-Request-ID before the log middleware tries to bind it), so it
    # is added AFTER RequestLogMiddleware.
    # Order after registration:
    #   Request → CorrelationId → RequestLog → CORS → BodySizeLimit → TrustedHost → App
    #
    # BodySizeLimitMiddleware sits INSIDE CorrelationId/RequestLog and CORS, and
    # every one of those placements is deliberate:
    #   - inside CorrelationId + RequestLog, so a 413 still carries X-Request-ID
    #     and still produces an access-log line. Outermost it would be invisible.
    #   - inside CORS, so the 413 carries the CORS headers a browser needs in
    #     order to read it at all.
    #   - outside the app, so an over-long body is never handed to route parsing.
    # The cost of being inside CORS is that a CORS preflight never reaches it —
    # CORSMiddleware answers those itself. Measured and accepted: a preflight body
    # is never delivered to the application, so bounding it would buy nothing at
    # this layer and would cost the 413 its CORS headers. See the module docstring
    # for the full scope of the guarantee, which is about bytes reaching route
    # parsing rather than bytes reaching the process.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(CorrelationIdMiddleware)


def _setup_container(app: FastAPI):
    container = create_server_container()
    app.state.container = container
    return container


def _bootstrap_quickstart_schema_if_applicable(container) -> None:
    """Auto-create tables from model metadata in quickstart mode only.

    ``make quickstart`` uses an empty SQLite file with no migrations.
    Real environments (local/dev/stg/prod) must use Alembic instead.
    """
    if settings.env.lower() == "quickstart":
        database: Database = container.core_container.database()
        Base.metadata.create_all(database.engine)


def _install_core_routes(app: FastAPI, container) -> None:
    # Wire core container for health check DI
    # (core is not a domain — no separate bootstrap file needed)
    container.core_container().wire(
        modules=["src._core.application.routers.api.health_check_router"]
    )

    app.include_router(router=health_check_router.router, tags=["status", "NEW"])
    if settings.is_dev:
        app.include_router(router=docs_router.router, tags=["docs"])


def _bootstrap_domains(app: FastAPI, container) -> None:
    """Dynamically bootstrap all domains detected by discover_domains().

    Domains without a server bootstrap module are silently skipped so that
    worker-only domains or admin-only domains do not crash the server boot.
    """
    for name in discover_domains():
        module_path = f"src.{name}.interface.server.bootstrap.{name}_bootstrap"
        try:
            module = importlib.import_module(module_path)
            bootstrap_fn = getattr(module, f"bootstrap_{name}_domain")
        except (ModuleNotFoundError, AttributeError):
            _logger.debug("domain_server_bootstrap_skipped", domain=name)
            continue

        domain_container = getattr(container, f"{name}_container")
        bootstrap_fn(
            app=app,
            **{f"{name}_container": domain_container},
        )


def _install_inline_task_runtime(container) -> None:
    """Give the inline broker the task runtime the worker process would give it (#324).

    Under ``BROKER_TYPE=inmemory`` — the shipped default, and a value that passes
    stg/prod validation — ``.kiq()`` executes the task **in this process**. But the
    middleware stack and the domain task wiring are installed by
    ``src/_apps/worker/bootstrap.py``, reached only through ``worker/app.py``,
    which the server never imports. Measured at HEAD in a server process:

        server-process broker : InMemoryBroker
        middlewares           : []
        registered tasks      : ['my-project.docs.ingest_document']

    So a task failure produced no retry, no ``task_error`` record, no #310 alert
    and no correlation-id binding — and the absence of the error-logging
    middleware is itself what hid the failure.

    Three things here are deliberate and each was measured:

    1. **The provider comes from the server's own core tree.** Passing the worker
       module's ``container.error_notifier`` would give this process two
       ``ErrorNotifier`` singletons, hence two ``NoopNotificationClient``s — two
       ``notification_client_disabled`` lines against the documented per-process
       invariant — and two independent cooldown dicts, so an HTTP-path alert would
       not suppress a duplicate task-path alert.

    2. **The server passes its OWN container to the domain wiring**, not a fresh
       ``create_worker_container(...)``. Building one would raise
       ``AttributeError: 'DependenciesContainer' object has no attribute
       '__self__'`` — the server has already overridden those class-level
       dependency containers.

    3. **Only the inline broker is touched.** With a cross-process broker the
       tasks run in a real worker that installs its own stack, and installing it
       here as well would double-register.

    A repeated ``bootstrap_app`` call is handled by ``install_task_middleware``
    itself, which rebinds the notifier's provider rather than appending a second
    stack. This used to be a ``not task_broker.middlewares`` guard here, which was
    wrong in a way the comment claimed it was right: it skipped installation but
    left the notifier holding the *first* container's ``error_notifier`` provider,
    so a second bootstrap re-wired the domain tasks to the new container while
    alert cooldowns kept keying off the discarded one.

    Not imported at module scope: ``src._apps.worker.broker`` constructs a
    ``CoreContainer`` at import time, and keeping that inside the function leaves
    the import graph as it was for anything that does not reach this step.
    """
    from taskiq import InMemoryBroker

    from src._apps.worker.bootstrap import (
        bootstrap_task_domains,
        install_task_middleware,
    )
    from src._apps.worker.broker import broker as task_broker
    from src._apps.worker.tasks import audit_cleanup_task as _audit_cleanup

    if not isinstance(task_broker, InMemoryBroker):
        return

    core_container = container.core_container()
    install_task_middleware(
        task_broker, error_notifier_provider=core_container.error_notifier
    )
    bootstrap_task_domains(container)
    # `bootstrap_task_domains` covers `src/{domain}/` tasks only. The audit
    # cleanup task lives under `_apps/worker/tasks/` and is wired by the worker
    # bootstrap, which this process never calls — so without this line it ran with
    # an unresolved `Provide[CoreContainer.database]` marker even though it *is*
    # registered on this broker and therefore dispatchable from here. Probed after
    # a server boot: `param database default_is_Provide=True`.
    #
    # Wiring against the server's core container is what makes the task use this
    # process's database. Placed after the domain containers exist, per the
    # ordering constraint `wire()` imposes (see worker/bootstrap.py).
    core_container.wire(modules=[_audit_cleanup])
    _logger.info(
        "inline_task_runtime_installed",
        middlewares=[type(m).__name__ for m in task_broker.middlewares],
        tasks=sorted(task_broker.get_all_tasks()),
    )


def _mount_admin_if_available(app: FastAPI) -> None:
    """Mount the NiceGUI admin dashboard if the ``admin`` extra is installed.

    If nicegui is absent the server still boots; admin routes are not mounted.
    The skip path emits a structured ``admin_mount_skipped`` record so
    operators can diagnose from logs without re-reading the README.
    """
    try:
        from src._apps.admin.bootstrap import bootstrap_admin
    except ImportError:
        _logger.info(
            "admin_mount_skipped",
            reason="nicegui_not_installed",
            install_hint="uv sync --extra admin",
        )
        return

    bootstrap_admin(app)
