import importlib

import structlog
from fastapi import FastAPI
from nicegui import app, ui

from src._apps.admin.di.container import create_admin_container
from src._apps.admin.pages import (
    accounts,  # noqa: F401 (registers @ui.page)
    audit_log,  # noqa: F401 (registers @ui.page)
    change_password,  # noqa: F401 (registers @ui.page)
    dashboard,  # noqa: F401 (registers @ui.page)
    error,  # noqa: F401 (registers @ui.page)
    login,  # noqa: F401 (registers @ui.page)
    setup,  # noqa: F401 (registers @ui.page)
)
from src._core.config import settings
from src._core.infrastructure.admin.audit import (  # noqa: F401 — also registers AdminAuditLog on Base.metadata for quickstart create_all()
    AdminAuditLogRepository,
)
from src._core.infrastructure.admin.audit.logger import (
    AuditLogger,
    configure_audit_logger,
    configure_audit_repository,
)
from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    configure_admin_account_use_case_provider,
    configure_admin_auth_provider,
)
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import (
    handle_uncaught_admin_exception,
)
from src._core.infrastructure.discovery import discover_domains
from src.user.domain.dtos.user_dto import BootstrapAdminUserDTO

_logger = structlog.stdlib.get_logger(__name__)

# Guards against duplicate registration of the global exception handler when
# bootstrap_admin() runs more than once in a process (e.g. test reloads).
_global_exception_handler_registered = False


def bootstrap_admin(fastapi_app: FastAPI) -> None:
    """Bootstrap NiceGUI admin dashboard onto the existing FastAPI app."""
    admin_container = create_admin_container()
    fastapi_app.state.admin_container = admin_container

    # Global safety net (#195): uniformly structured-log any exception that
    # escapes a page handler, event callback, or timer — even where a local
    # try/except or @admin_error_boundary did not catch it. Registered once per
    # process to avoid duplicate-log accumulation on repeated bootstrap calls.
    global _global_exception_handler_registered
    if not _global_exception_handler_registered:
        app.on_exception(handle_uncaught_admin_exception)
        _global_exception_handler_registered = True
    configure_admin_auth_provider(
        AdminAuthProvider(
            auth_use_case_provider=admin_container.auth_container.auth_use_case
        )
    )
    # Wire the audit infrastructure (#196 Phase 1 + #206 Phase 2) before any
    # admin action can fire. The logger and the repository share the same
    # instance — the logger uses it for writes, the audit-log UI for queries,
    # and the cleanup task for retention deletes.
    database = admin_container.core_container.database()
    audit_repo = AdminAuditLogRepository(database)
    configure_audit_repository(audit_repo)
    configure_audit_logger(AuditLogger(audit_repo))
    configure_admin_account_use_case_provider(
        admin_container.auth_container.admin_account_use_case
    )
    _install_bootstrap_admin_seed(fastapi_app, admin_container)

    # Shared list — domain pages and dashboard both reference this same object.
    # Pages are rendered at request time, so all entries are present by then.
    page_configs: list[BaseAdminPage] = []
    _discover_and_register_pages(page_configs, admin_container)

    dashboard.page_configs = page_configs
    accounts.page_configs = page_configs
    audit_log.page_configs = page_configs
    change_password.page_configs = page_configs

    # Populate the permission registry from successfully registered page_configs.
    # Fixed keys (e.g. 'accounts') are pre-seeded in the registry; domain keys are added here.
    permission_registry = admin_container.auth_container.permission_registry()
    for cfg in page_configs:
        permission_registry.register(cfg.domain_name)

    ui.run_with(fastapi_app, storage_secret=settings.admin_storage_secret)


def _install_bootstrap_admin_seed(fastapi_app: FastAPI, admin_container) -> None:
    if not settings.admin_bootstrap_enabled:
        return

    async def _seed_admin_user() -> None:
        password = settings.admin_bootstrap_password
        if not password:
            return
        service = admin_container.user_container.user_service()
        user = await service.ensure_admin_user(
            BootstrapAdminUserDTO(
                username=settings.admin_bootstrap_username,
                full_name=settings.admin_bootstrap_full_name,
                email=settings.admin_bootstrap_email,
                password=password,
            )
        )
        if user is not None:
            _logger.info(
                "admin_bootstrap_user_ready",
                user_id=user.id,
                username=user.username,
            )
        else:
            _logger.info("admin_bootstrap_seed_skipped")

    fastapi_app.add_event_handler("startup", _seed_admin_user)


def _discover_and_register_pages(
    page_configs: list[BaseAdminPage], admin_container
) -> None:
    """Auto-discover admin pages: import config, register routes, wire DI."""
    for name in discover_domains():
        try:
            # 1) Config: BaseAdminPage 선언 가져오기
            config_module_path = (
                f"src.{name}.interface.admin.configs.{name}_admin_config"
            )
            config_module = importlib.import_module(config_module_path)
            page_config = getattr(config_module, f"{name}_admin_page")
            page_configs.append(page_config)

            # 2) DI: 서비스 프로바이더 주입
            domain_container = getattr(admin_container, f"{name}_container")
            page_config._service_provider = getattr(domain_container, f"{name}_service")

            # 3) Extra services: wire any services declared in extra_services_config
            for alias, attr_name in page_config.extra_services_config.items():
                provider = getattr(domain_container, attr_name, None)
                if provider is not None:
                    page_config._extra_services[alias] = provider

            # 4) Routes: 모듈 import로 @ui.page 등록 트리거 + page_configs 주입
            page_module_path = f"src.{name}.interface.admin.pages.{name}_page"
            page_module = importlib.import_module(page_module_path)
            page_module.page_configs = page_configs
        except (ModuleNotFoundError, AttributeError):
            continue
