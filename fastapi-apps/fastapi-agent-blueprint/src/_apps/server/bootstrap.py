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
from src._core.infrastructure.discovery import discover_domains
from src._core.infrastructure.logging.configure import configure_logging
from src._core.infrastructure.logging.request_log_middleware import (
    RequestLogMiddleware,
)
from src._core.infrastructure.persistence.rdb.database import Base, Database

_logger = structlog.stdlib.get_logger("src._apps.server.bootstrap")


def bootstrap_app(app: FastAPI) -> None:
    _configure_logging_pipeline()
    _maybe_configure_otel(service_name="fastapi-agent-blueprint-server")
    _install_exception_handlers(app)
    _install_middleware(app)
    container = _setup_container(app)
    _bootstrap_quickstart_schema_if_applicable(container)
    _install_core_routes(app, container)
    _bootstrap_domains(app, container)
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
    # Order after registration: Request → CorrelationId → RequestLog → CORS → TrustedHost → App
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
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


def _maybe_configure_otel(service_name: str) -> None:
    """Configure OpenTelemetry tracing if enabled and the otel extra is installed.

    If the extra is missing the server still boots; the skip is recorded as a
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
