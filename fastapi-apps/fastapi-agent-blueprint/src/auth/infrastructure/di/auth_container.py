from dependency_injector import containers, providers

from src._core.config import settings
from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.domain.dtos.auth_dto import AuthTokenConfig
from src.auth.domain.services.auth_service import AuthService
from src.auth.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.user.domain.services.user_service import UserService
from src.user.infrastructure.repositories.user_repository import UserRepository


class AuthContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    refresh_token_repository = providers.Singleton(
        RefreshTokenRepository,
        database=core_container.database,
    )

    user_repository = providers.Singleton(
        UserRepository,
        database=core_container.database,
    )

    user_service = providers.Factory(
        UserService,
        user_repository=user_repository,
    )

    token_config = providers.Factory(
        AuthTokenConfig,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_minutes=settings.jwt_access_token_minutes,
        refresh_token_days=settings.jwt_refresh_token_days,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        leeway_seconds=settings.jwt_leeway_seconds,
    )

    auth_service = providers.Factory(
        AuthService,
        refresh_token_repository=refresh_token_repository,
        user_repository=user_repository,
        token_config=token_config,
    )

    auth_use_case = providers.Factory(
        AuthUseCase,
        auth_service=auth_service,
        user_service=user_service,
        token_config=token_config,
    )
