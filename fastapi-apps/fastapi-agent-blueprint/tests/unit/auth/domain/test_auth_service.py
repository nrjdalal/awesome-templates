from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from pydantic import BaseModel

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

    async def has_real_admin(self) -> bool:
        return False

    async def delete_data_by_username(self, username: str) -> bool:
        return False

    async def count_accounts_permission_holders(
        self, exclude_user_id: int | None = None
    ) -> int:
        return 0

    async def select_all_admins(self) -> list[UserDTO]:
        return []

    async def insert_data(self, entity) -> UserDTO:  # type: ignore[override]
        raise NotImplementedError

    async def insert_datas(self, entities) -> list[UserDTO]:
        raise NotImplementedError

    async def select_datas(self, page: int, page_size: int) -> list[UserDTO]:
        return list(self._users.values())

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[UserDTO]:
        return [self._users[i] for i in data_ids if i in self._users]

    async def exists_by_id(self, data_id: int) -> bool:
        return data_id in self._users

    async def exists_by_fields(self, filters, *, exclude_id=None) -> bool:
        return False

    async def existing_values_by_field(
        self, field: str, values: list, *, exclude_id=None
    ) -> set:
        return set()

    async def select_datas_with_count(
        self, page: int, page_size: int, query_filter=None
    ) -> tuple[list[UserDTO], int]:
        items = list(self._users.values())
        return items, len(items)

    async def update_data_by_data_id(self, data_id: int, entity) -> UserDTO:
        raise NotImplementedError

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        self._users.pop(data_id, None)
        return True

    async def count_datas(self) -> int:
        return len(self._users)


class MockRefreshTokenRepository:
    def __init__(self) -> None:
        self._store: dict[str, RefreshTokenDTO] = {}
        self._next_id = 1

    async def insert_data(self, entity: BaseModel) -> RefreshTokenDTO:
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

    async def insert_datas(self, entities) -> list[RefreshTokenDTO]:
        raise NotImplementedError

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

    async def revoke_all_by_user_id(self, user_id: int) -> int:
        revoked = 0
        now = datetime.now(UTC)
        for jti, dto in self._store.items():
            if dto.user_id == user_id and dto.revoked_at is None:
                self._store[jti] = dto.model_copy(update={"revoked_at": now})
                revoked += 1
        return revoked

    async def select_datas(self, page: int, page_size: int) -> list[RefreshTokenDTO]:
        return list(self._store.values())

    async def select_data_by_id(self, data_id: int) -> RefreshTokenDTO:
        raise NotImplementedError

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[RefreshTokenDTO]:
        raise NotImplementedError

    async def exists_by_id(self, data_id: int) -> bool:
        return False

    async def exists_by_fields(self, filters, *, exclude_id=None) -> bool:
        return False

    async def existing_values_by_field(
        self, field: str, values: list, *, exclude_id=None
    ) -> set:
        return set()

    async def select_datas_with_count(
        self, page: int, page_size: int, query_filter=None
    ) -> tuple[list[RefreshTokenDTO], int]:
        items = list(self._store.values())
        return items, len(items)

    async def update_data_by_data_id(self, data_id: int, entity) -> RefreshTokenDTO:
        raise NotImplementedError

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        return False

    async def count_datas(self) -> int:
        return len(self._store)


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
