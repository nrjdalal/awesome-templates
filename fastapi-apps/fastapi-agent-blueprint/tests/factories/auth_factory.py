from datetime import UTC, datetime, timedelta

from src._core.config import settings
from src.auth.domain.dtos.auth_dto import (
    AuthTokenConfig,
    RefreshTokenCreateDTO,
    RefreshTokenDTO,
)
from src.auth.interface.server.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
)


def make_auth_token_config() -> AuthTokenConfig:
    return AuthTokenConfig(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_minutes=settings.jwt_access_token_minutes,
        refresh_token_days=settings.jwt_refresh_token_days,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        leeway_seconds=settings.jwt_leeway_seconds,
    )


def make_refresh_token_dto(
    id: int = 1,
    user_id: int = 1,
    token_hash: str = "0" * 64,
    jti: str = "test-jti",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> RefreshTokenDTO:
    now = datetime.now(UTC)
    return RefreshTokenDTO(
        id=id,
        user_id=user_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at or now + timedelta(days=14),
        revoked_at=revoked_at,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_refresh_token_create_dto(
    user_id: int = 1,
    token_hash: str = "0" * 64,
    jti: str = "test-jti",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> RefreshTokenCreateDTO:
    return RefreshTokenCreateDTO(
        user_id=user_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=14),
        revoked_at=revoked_at,
    )


def make_register_request(
    username: str = "authuser",
    full_name: str = "Auth User",
    email: str = "auth@example.com",
    password: str = "secret",
) -> RegisterRequest:
    return RegisterRequest(
        username=username,
        full_name=full_name,
        email=email,
        password=password,
    )


def make_login_request(
    username: str = "authuser",
    password: str = "secret",
) -> LoginRequest:
    return LoginRequest(username=username, password=password)


def make_refresh_request(refresh_token: str) -> RefreshTokenRequest:
    return RefreshTokenRequest(refresh_token=refresh_token)


def make_logout_request(refresh_token: str) -> LogoutRequest:
    return LogoutRequest(refresh_token=refresh_token)
