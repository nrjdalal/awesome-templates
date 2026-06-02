from dependency_injector import containers, providers

from src._core.config import settings
from src._core.infrastructure.admin.permission_registry import AdminPermissionRegistry
from src.admin_identity.application.use_cases.admin_account_use_case import (
    AdminAccountUseCase,
)
from src.admin_identity.application.use_cases.admin_auth_use_case import (
    AdminAuthUseCase,
)
from src.admin_identity.domain.dtos.admin_identity_dto import AdminTokenConfig
from src.admin_identity.domain.services.admin_auth_service import AdminAuthService
from src.admin_identity.domain.services.admin_identity_service import (
    AdminIdentityService,
)
from src.admin_identity.infrastructure.repositories.admin_identity_repository import (
    AdminIdentityRepository,
)
from src.admin_identity.infrastructure.repositories.admin_refresh_token_repository import (  # noqa: E501
    AdminRefreshTokenRepository,
)


class AdminIdentityContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    admin_repository = providers.Singleton(
        AdminIdentityRepository,
        database=core_container.database,
    )

    admin_refresh_token_repository = providers.Singleton(
        AdminRefreshTokenRepository,
        database=core_container.database,
    )

    admin_identity_service = providers.Factory(
        AdminIdentityService,
        admin_repository=admin_repository,
    )

    # Separate admin token realm (ADR 049): distinct secret / issuer / audience.
    admin_token_config = providers.Factory(
        AdminTokenConfig,
        secret_key=settings.admin_jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_minutes=settings.admin_jwt_access_token_minutes,
        refresh_token_days=settings.admin_jwt_refresh_token_days,
        issuer=settings.admin_jwt_issuer,
        audience=settings.admin_jwt_audience,
        leeway_seconds=settings.jwt_leeway_seconds,
    )

    admin_auth_service = providers.Factory(
        AdminAuthService,
        admin_refresh_token_repository=admin_refresh_token_repository,
        admin_repository=admin_repository,
        token_config=admin_token_config,
    )

    admin_auth_use_case = providers.Factory(
        AdminAuthUseCase,
        admin_auth_service=admin_auth_service,
        admin_identity_service=admin_identity_service,
        token_config=admin_token_config,
    )

    permission_registry = providers.Singleton(AdminPermissionRegistry)

    admin_account_use_case = providers.Factory(
        AdminAccountUseCase,
        admin_auth_service=admin_auth_service,
        admin_identity_service=admin_identity_service,
        permission_registry=permission_registry,
    )
