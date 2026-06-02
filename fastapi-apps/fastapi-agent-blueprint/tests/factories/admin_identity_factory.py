from datetime import UTC, datetime, timedelta

from src._core.config import settings
from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    AdminRefreshTokenCreateDTO,
    AdminRefreshTokenDTO,
    AdminTokenConfig,
)
from src.admin_identity.interface.server.schemas.admin_auth_schema import (
    AdminLoginRequest,
    AdminLogoutRequest,
)


def make_admin_token_config() -> AdminTokenConfig:
    return AdminTokenConfig(
        secret_key=settings.admin_jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_minutes=settings.admin_jwt_access_token_minutes,
        refresh_token_days=settings.admin_jwt_refresh_token_days,
        issuer=settings.admin_jwt_issuer,
        audience=settings.admin_jwt_audience,
        leeway_seconds=settings.jwt_leeway_seconds,
    )


def make_admin_identity_dto(
    id: int = 1,
    username: str = "admin",
    full_name: str = "Admin User",
    email: str = "admin@example.com",
    password: str = "hashed_password",
    permissions: list[str] | None = None,
    password_temporary: bool = False,
    is_bootstrap_admin: bool = False,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> AdminIdentityDTO:
    now = datetime.now()
    return AdminIdentityDTO(
        id=id,
        username=username,
        full_name=full_name,
        email=email,
        password=password,
        permissions=permissions if permissions is not None else [],
        password_temporary=password_temporary,
        is_bootstrap_admin=is_bootstrap_admin,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_admin_refresh_token_dto(
    id: int = 1,
    admin_id: int = 1,
    token_hash: str = "0" * 64,
    jti: str = "test-jti",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> AdminRefreshTokenDTO:
    now = datetime.now(UTC)
    return AdminRefreshTokenDTO(
        id=id,
        admin_id=admin_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at or now + timedelta(days=7),
        revoked_at=revoked_at,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_admin_refresh_token_create_dto(
    admin_id: int = 1,
    token_hash: str = "0" * 64,
    jti: str = "test-jti",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> AdminRefreshTokenCreateDTO:
    return AdminRefreshTokenCreateDTO(
        admin_id=admin_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=7),
        revoked_at=revoked_at,
    )


def make_admin_login_request(
    username: str = "admin",
    password: str = "secret",
) -> AdminLoginRequest:
    return AdminLoginRequest(username=username, password=password)


def make_admin_logout_request(refresh_token: str) -> AdminLogoutRequest:
    return AdminLogoutRequest(refresh_token=refresh_token)
