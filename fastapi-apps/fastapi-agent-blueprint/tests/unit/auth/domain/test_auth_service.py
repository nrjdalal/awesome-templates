from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from src._core.common.security import hash_password
from src.auth.domain.dtos.auth_dto import RefreshTokenCreateDTO, RefreshTokenDTO
from src.auth.domain.exceptions.auth_exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    RefreshTokenRevokedException,
    TokenExpiredException,
)
from src.auth.domain.services.auth_service import AuthService
from src.user.domain.dtos.user_dto import UserDTO
from tests.factories.auth_factory import make_auth_token_config
from tests.factories.user_factory import make_user_dto


class MockUserRepository:
    def __init__(self, users: list[UserDTO] | None = None) -> None:
        self._users = {user.id: user for user in users or []}

    async def select_data_by_username(self, username: str) -> UserDTO | None:
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    async def select_data_by_id(self, data_id: int) -> UserDTO:
        return self._users[data_id]


class MockRefreshTokenRepository:
    def __init__(self) -> None:
        self._store: dict[str, RefreshTokenDTO] = {}
        self._next_id = 1

    async def insert_data(self, entity: RefreshTokenCreateDTO) -> RefreshTokenDTO:
        now = datetime.now(UTC)
        dto = RefreshTokenDTO(
            id=self._next_id,
            created_at=now,
            updated_at=now,
            **entity.model_dump(),
        )
        self._store[dto.jti] = dto
        self._next_id += 1
        return dto

    async def select_data_by_jti(self, jti: str) -> RefreshTokenDTO | None:
        return self._store.get(jti)

    async def revoke_by_jti(self, jti: str) -> RefreshTokenDTO | None:
        dto = self._store.get(jti)
        if dto is None:
            return None
        if dto.revoked_at is not None:
            return None
        revoked = dto.model_copy(update={"revoked_at": datetime.now(UTC)})
        self._store[jti] = revoked
        return revoked


@pytest.fixture
def user() -> UserDTO:
    return make_user_dto(password=hash_password("secret"))


@pytest.fixture
def refresh_repo() -> MockRefreshTokenRepository:
    return MockRefreshTokenRepository()


@pytest.fixture
def auth_service(user, refresh_repo) -> AuthService:
    return AuthService(
        refresh_token_repository=refresh_repo,
        user_repository=MockUserRepository([user]),
        token_config=make_auth_token_config(),
    )


@pytest.mark.asyncio
async def test_verify_credentials_accepts_hashed_password(auth_service, user):
    result = await auth_service.verify_credentials(user.username, "secret")

    assert result.id == user.id


@pytest.mark.asyncio
async def test_verify_credentials_rejects_invalid_password(auth_service, user):
    with pytest.raises(InvalidCredentialsException):
        await auth_service.verify_credentials(user.username, "wrong")


@pytest.mark.asyncio
async def test_access_token_returns_current_user(auth_service, user):
    access_token, _ = await auth_service.issue_token_pair(user)

    result = await auth_service.get_user_from_access_token(access_token)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_token_claims_do_not_include_role(auth_service, user):
    token_config = make_auth_token_config()
    access_token, refresh_token = await auth_service.issue_token_pair(user)

    for token in (access_token, refresh_token):
        payload = jwt.decode(
            token,
            token_config.secret_key,
            algorithms=[token_config.algorithm],
            audience=token_config.audience,
            issuer=token_config.issuer,
        )
        assert set(payload) == {"sub", "jti", "type", "iat", "exp", "iss", "aud"}
        assert "role" not in payload


@pytest.mark.asyncio
async def test_refresh_token_is_rejected_on_access_dependency(auth_service, user):
    _, refresh_token = await auth_service.issue_token_pair(user)

    with pytest.raises(InvalidTokenException):
        await auth_service.get_user_from_access_token(refresh_token)


@pytest.mark.asyncio
async def test_refresh_token_rotates_single_use(auth_service, user):
    _, refresh_token = await auth_service.issue_token_pair(user)

    access_token, next_refresh_token = await auth_service.rotate_refresh_token(
        refresh_token
    )

    assert access_token != refresh_token
    assert next_refresh_token != refresh_token
    with pytest.raises(RefreshTokenRevokedException):
        await auth_service.rotate_refresh_token(refresh_token)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(auth_service, user):
    _, refresh_token = await auth_service.issue_token_pair(user)

    assert await auth_service.revoke_refresh_token(refresh_token) is True
    assert await auth_service.revoke_refresh_token(refresh_token) is True

    with pytest.raises(RefreshTokenRevokedException):
        await auth_service.rotate_refresh_token(refresh_token)


@pytest.mark.asyncio
async def test_expired_access_token_is_rejected(auth_service):
    token_config = make_auth_token_config()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": "1",
        "jti": "expired",
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "iss": token_config.issuer,
        "aud": token_config.audience,
    }
    token = jwt.encode(
        payload, token_config.secret_key, algorithm=token_config.algorithm
    )

    with pytest.raises(TokenExpiredException):
        await auth_service.get_user_from_access_token(token)
