import importlib

import structlog
from taskiq import AsyncBroker, TaskiqState

from src._apps.worker.broker import container
from src._apps.worker.di.container import create_worker_container

# Cross-cutting worker tasks that live outside ``src/{domain}/`` are not
# auto-discovered by ``_bootstrap_domains`` — import them explicitly here so
# the ``@broker.task`` decorator registers them with the broker before the
# worker starts pulling jobs (#206 audit retention cleanup).
from src._apps.worker.tasks import audit_cleanup_task as _audit_cleanup  # noqa: F401

# Wire ``Provide[CoreContainer.database]`` markers in the cross-cutting tasks
# at module-import time so resolution works in BOTH process families:
# - worker process (executes the task)
# - scheduler process (introspects @broker.task schedule labels)
# Without module-level wire, the wire call inside the startup event only runs
# in the worker — scheduler-side direct invocation would hit an unresolved
# Provide marker.
container.wire(modules=[_audit_cleanup])
from src._core.config import settings
from src._core.infrastructure.discovery import discover_domains
from src._core.infrastructure.logging.configure import configure_logging
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
)

_logger = structlog.stdlib.get_logger("src._apps.worker.bootstrap")


def bootstrap_app(app: AsyncBroker) -> None:
    _configure_logging_pipeline()
    _maybe_configure_otel(service_name="fastapi-agent-blueprint-worker")
    _install_middleware(app)
    _register_startup_event(app)


# ---------------------------------------------------------------------------
# Private orchestration steps
# ---------------------------------------------------------------------------


def _configure_logging_pipeline() -> None:
    """Configure structlog before any task can run."""
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.effective_log_json,
    )


def _install_middleware(app: AsyncBroker) -> None:
    """Bind task context, log failures, and retry transient task errors."""
    app.add_middlewares(
        StructlogContextMiddleware(),
        PermanentAwareSmartRetryMiddleware(),
        TaskErrorLoggingMiddleware(),
    )


def _register_startup_event(app: AsyncBroker) -> None:
    @app.on_event("startup")
    async def startup(state: TaskiqState):
        worker_container = create_worker_container(core_container=container)
        _bootstrap_domains(worker_container=worker_container)


def _maybe_configure_otel(service_name: str) -> None:
    """Configure OpenTelemetry tracing if enabled and the otel extra is installed.

    If the extra is missing the worker still boots; the skip is recorded as a
    structured log line so operators can diagnose without re-reading the README.
    """
    if not settings.otel_enabled:
        return
    try:
        from src._core.infrastructure.observability.otel_setup import configure_otel
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("opentelemetry"):
            raise
        _logger.warning(
            "otel_extra_not_installed",
            install_hint="uv sync --extra otel",
        )
        return
    configure_otel(settings, service_name=service_name)


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
