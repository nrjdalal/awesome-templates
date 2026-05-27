from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel

from src._core.common.security import hash_password, verify_password
from src._core.infrastructure.admin.permission_registry import AdminPermissionRegistry
from src.auth.application.use_cases.admin_account_use_case import AdminAccountUseCase
from src.auth.domain.exceptions.auth_exceptions import (
    AdminLastAccountsGuardException,
    AdminSelfActionForbiddenException,
    AdminSetupForbiddenException,
    InvalidCredentialsException,
)
from src.user.domain.dtos.user_dto import (
    USER_ROLE_ADMIN,
    CreateAdminAccountDTO,
    UserDTO,
)
from src.user.domain.services.user_service import UserService
from tests.factories.user_factory import make_user_dto

# ── Fakes ──────────────────────────────────────────────────────────────────


class FakeUserRepository:
    """Minimal in-memory repository that satisfies UserService + AdminAccountUseCase."""

    def __init__(self, users: list[UserDTO] | None = None) -> None:
        self._store: dict[int, UserDTO] = {u.id: u for u in (users or [])}
        self._next_id = max((u.id for u in (users or [])), default=0) + 1
        self.deleted_ids: list[int] = []
        self.deleted_usernames: list[str] = []

    async def insert_data(self, entity: BaseModel) -> UserDTO:
        data = entity.model_dump()
        dto = make_user_dto(id=self._next_id, **data)
        self._store[self._next_id] = dto
        self._next_id += 1
        return dto

    async def select_data_by_id(self, data_id: int) -> UserDTO:
        return self._store[data_id]

    async def select_data_by_username(self, username: str) -> UserDTO | None:
        for dto in self._store.values():
            if dto.username == username:
                return dto
        return None

    async def update_data_by_data_id(self, data_id: int, entity: BaseModel) -> UserDTO:
        dto = self._store[data_id]
        updated = dto.model_copy(
            update={k: v for k, v in entity.model_dump().items() if v is not None}
        )
        self._store[data_id] = updated
        return updated

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        self.deleted_ids.append(data_id)
        self._store.pop(data_id, None)
        return True

    async def delete_data_by_username(self, username: str) -> bool:
        self.deleted_usernames.append(username)
        for data_id, dto in list(self._store.items()):
            if dto.username == username:
                del self._store[data_id]
                return True
        return False

    async def has_real_admin(self) -> bool:
        return any(
            dto.role == USER_ROLE_ADMIN and not dto.is_bootstrap_admin
            for dto in self._store.values()
        )

    async def count_accounts_permission_holders(
        self, exclude_user_id: int | None = None
    ) -> int:
        return sum(
            1
            for data_id, dto in self._store.items()
            if "accounts" in (dto.permissions or [])
            and (exclude_user_id is None or data_id != exclude_user_id)
        )

    async def select_all_admins(self) -> list[UserDTO]:
        return [dto for dto in self._store.values() if dto.role == USER_ROLE_ADMIN]

    async def exists_by_fields(
        self, filters: Mapping[str, Any], *, exclude_id: int | None = None
    ) -> bool:
        for data_id, dto in self._store.items():
            if exclude_id is not None and data_id == exclude_id:
                continue
            if all(getattr(dto, field) == value for field, value in filters.items()):
                return True
        return False

    async def existing_values_by_field(
        self, field: str, values: list[Any], *, exclude_id: int | None = None
    ) -> set[Any]:
        value_set = set(values)
        return {
            getattr(dto, field)
            for data_id, dto in self._store.items()
            if (exclude_id is None or data_id != exclude_id)
            and getattr(dto, field) in value_set
        }

    async def insert_datas(self, entities: list[BaseModel]) -> list[UserDTO]:
        return [await self.insert_data(e) for e in entities]

    async def select_datas(self, page: int, page_size: int) -> list[UserDTO]:
        items = list(self._store.values())
        start = (page - 1) * page_size
        return items[start : start + page_size]

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[UserDTO]:
        return [self._store[i] for i in data_ids if i in self._store]

    async def exists_by_id(self, data_id: int) -> bool:
        return data_id in self._store

    async def select_datas_with_count(
        self, page: int = 1, page_size: int = 20, query_filter=None
    ) -> tuple[list[UserDTO], int]:
        del page, page_size, query_filter
        items = list(self._store.values())
        return items, len(items)

    async def count_datas(self) -> int:
        return len(self._store)


class FakeAuthService:
    def __init__(self, user: UserDTO | None = None, tokens_revoked: int = 2) -> None:
        self._user = user
        self._tokens_revoked = tokens_revoked
        self.revoke_calls: list[int] = []

    async def verify_credentials(self, username: str, password: str) -> UserDTO:
        if self._user and self._user.username == username:
            if verify_password(password, self._user.password):
                return self._user
        raise InvalidCredentialsException()

    async def get_user_by_id(self, user_id: int) -> UserDTO:
        if self._user and self._user.id == user_id:
            return self._user
        raise InvalidCredentialsException()

    async def revoke_all_tokens_for_user(self, user_id: int) -> int:
        self.revoke_calls.append(user_id)
        return self._tokens_revoked


def _make_registry(*extra_keys: str) -> AdminPermissionRegistry:
    registry = AdminPermissionRegistry()
    for key in extra_keys:
        registry.register(key)
    return registry


def _make_use_case(
    users: list[UserDTO] | None = None,
    auth_user: UserDTO | None = None,
    *,
    extra_keys: tuple[str, ...] = (),
) -> tuple[AdminAccountUseCase, FakeUserRepository, FakeAuthService]:
    repo = FakeUserRepository(users)
    user_service = UserService(user_repository=repo)
    auth_service = FakeAuthService(auth_user)
    registry = _make_registry(*extra_keys)
    use_case = AdminAccountUseCase(
        auth_service=auth_service,  # type: ignore[arg-type]
        user_service=user_service,
        permission_registry=registry,
    )
    return use_case, repo, auth_service


# ── Tests: get_available_permission_keys ──────────────────────────────────


def test_get_available_permission_keys_always_includes_accounts():
    use_case, _, _ = _make_use_case()
    keys = use_case.get_available_permission_keys()
    assert "accounts" in keys


def test_get_available_permission_keys_includes_registered_pages():
    use_case, _, _ = _make_use_case(extra_keys=("docs", "user"))
    keys = use_case.get_available_permission_keys()
    assert "docs" in keys
    assert "user" in keys
    assert "accounts" in keys


# ── Tests: verify_bootstrap_for_setup ─────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_bootstrap_for_setup_raises_when_real_admin_exists():
    real_admin = make_user_dto(
        id=1, username="realadmin", role=USER_ROLE_ADMIN, is_bootstrap_admin=False
    )
    bootstrap = make_user_dto(
        id=2,
        username="admin",
        password=hash_password("adminpass"),
        role=USER_ROLE_ADMIN,
        is_bootstrap_admin=True,
    )
    use_case, _, _ = _make_use_case([real_admin, bootstrap], auth_user=bootstrap)

    with pytest.raises(AdminSetupForbiddenException):
        await use_case.verify_bootstrap_for_setup("admin", "adminpass")


@pytest.mark.asyncio
async def test_verify_bootstrap_for_setup_raises_for_non_bootstrap_user():
    regular_user = make_user_dto(
        id=1,
        username="user",
        password=hash_password("pass"),
        role=USER_ROLE_ADMIN,
        is_bootstrap_admin=False,
    )
    use_case, _, _ = _make_use_case([regular_user], auth_user=regular_user)

    with pytest.raises(AdminSetupForbiddenException):
        await use_case.verify_bootstrap_for_setup("user", "pass")


@pytest.mark.asyncio
async def test_verify_bootstrap_for_setup_raises_on_wrong_credentials():
    bootstrap = make_user_dto(
        id=1,
        username="admin",
        password=hash_password("secret"),
        role=USER_ROLE_ADMIN,
        is_bootstrap_admin=True,
    )
    use_case, _, _ = _make_use_case([bootstrap], auth_user=bootstrap)

    with pytest.raises(InvalidCredentialsException):
        await use_case.verify_bootstrap_for_setup("admin", "wrongpass")


@pytest.mark.asyncio
async def test_verify_bootstrap_for_setup_succeeds_for_bootstrap_user():
    bootstrap = make_user_dto(
        id=1,
        username="admin",
        password=hash_password("adminpass"),
        role=USER_ROLE_ADMIN,
        is_bootstrap_admin=True,
    )
    use_case, _, _ = _make_use_case([bootstrap], auth_user=bootstrap)

    # Should not raise
    await use_case.verify_bootstrap_for_setup("admin", "adminpass")


# ── Tests: create_first_admin ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_first_admin_creates_real_admin_and_deletes_bootstrap():
    bootstrap = make_user_dto(
        id=1,
        username="admin",
        role=USER_ROLE_ADMIN,
        is_bootstrap_admin=True,
    )
    use_case, repo, _ = _make_use_case([bootstrap], extra_keys=("docs",))

    new_admin, temp_password = await use_case.create_first_admin(
        username="firstadmin",
        full_name="First Admin",
        email="first@example.com",
        bootstrap_username="admin",
    )

    assert new_admin.username == "firstadmin"
    assert temp_password  # non-empty
    assert len(temp_password) >= 16
    assert "admin" in repo.deleted_usernames


@pytest.mark.asyncio
async def test_create_first_admin_grants_all_registered_permissions():
    bootstrap = make_user_dto(
        id=1, username="admin", role=USER_ROLE_ADMIN, is_bootstrap_admin=True
    )
    use_case, _, _ = _make_use_case([bootstrap], extra_keys=("docs", "user"))

    new_admin, _ = await use_case.create_first_admin(
        username="firstadmin",
        full_name="First Admin",
        email="first@example.com",
        bootstrap_username="admin",
    )

    assert "docs" in new_admin.permissions
    assert "user" in new_admin.permissions
    assert "accounts" in new_admin.permissions


@pytest.mark.asyncio
async def test_create_first_admin_race_guard_raises_when_real_admin_exists():
    real_admin = make_user_dto(
        id=1, username="realadmin", role=USER_ROLE_ADMIN, is_bootstrap_admin=False
    )
    bootstrap = make_user_dto(
        id=2, username="admin", role=USER_ROLE_ADMIN, is_bootstrap_admin=True
    )
    use_case, _, _ = _make_use_case([real_admin, bootstrap])

    with pytest.raises(AdminSetupForbiddenException):
        await use_case.create_first_admin(
            username="another",
            full_name="Another",
            email="another@example.com",
            bootstrap_username="admin",
        )


# ── Tests: create_account ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_account_returns_new_admin_and_temp_password():
    use_case, _, _ = _make_use_case()

    dto = CreateAdminAccountDTO(
        username="newadmin",
        full_name="New Admin",
        email="new@example.com",
        permissions=["docs"],
    )
    new_admin, temp_password = await use_case.create_account(dto)

    assert new_admin.username == "newadmin"
    assert temp_password
    assert len(temp_password) >= 16


@pytest.mark.asyncio
async def test_create_account_temp_password_not_same_across_calls():
    use_case, _, _ = _make_use_case()

    dto1 = CreateAdminAccountDTO(
        username="admin1", full_name="A1", email="a1@example.com"
    )
    dto2 = CreateAdminAccountDTO(
        username="admin2", full_name="A2", email="a2@example.com"
    )
    _, pw1 = await use_case.create_account(dto1)
    _, pw2 = await use_case.create_account(dto2)

    assert pw1 != pw2


# ── Tests: delete_account ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_account_raises_on_self_delete():
    admin = make_user_dto(
        id=1, username="admin", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    use_case, _, _ = _make_use_case([admin])

    with pytest.raises(AdminSelfActionForbiddenException):
        await use_case.delete_account(admin_id=1, requesting_admin_id=1)


@pytest.mark.asyncio
async def test_delete_account_raises_when_target_is_last_accounts_holder():
    admin1 = make_user_dto(
        id=1, username="admin1", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    admin2 = make_user_dto(
        id=2, username="admin2", role=USER_ROLE_ADMIN, permissions=["docs"]
    )
    use_case, _, _ = _make_use_case([admin1, admin2])

    # admin1 is the only accounts-permission holder; deleting it would lock everyone out
    with pytest.raises(AdminLastAccountsGuardException):
        await use_case.delete_account(admin_id=1, requesting_admin_id=2)


@pytest.mark.asyncio
async def test_delete_account_succeeds_when_another_accounts_holder_remains():
    admin1 = make_user_dto(
        id=1, username="admin1", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    admin2 = make_user_dto(
        id=2, username="admin2", role=USER_ROLE_ADMIN, permissions=["accounts", "docs"]
    )
    use_case, repo, _ = _make_use_case([admin1, admin2])

    await use_case.delete_account(admin_id=1, requesting_admin_id=2)

    assert 1 in repo.deleted_ids


# ── Tests: update_permissions ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_permissions_strips_keys_not_in_registry():
    admin = make_user_dto(
        id=1, username="admin", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    use_case, _, _ = _make_use_case([admin], extra_keys=("docs",))

    result = await use_case.update_permissions(
        admin_id=1,
        permissions=["docs", "nonexistent_page", "accounts"],
        requesting_admin_id=2,
    )

    assert "docs" in result.permissions
    assert "accounts" in result.permissions
    assert "nonexistent_page" not in result.permissions


@pytest.mark.asyncio
async def test_update_permissions_guards_self_lockout_as_last_accounts_holder():
    admin = make_user_dto(
        id=1, username="admin", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    use_case, _, _ = _make_use_case([admin])

    # Admin tries to remove their own accounts permission; they're the last holder
    with pytest.raises(AdminLastAccountsGuardException):
        await use_case.update_permissions(
            admin_id=1,
            permissions=["docs"],  # no "accounts"
            requesting_admin_id=1,
        )


@pytest.mark.asyncio
async def test_update_permissions_allows_self_lockout_when_another_accounts_holder():
    admin1 = make_user_dto(
        id=1, username="admin1", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    admin2 = make_user_dto(
        id=2, username="admin2", role=USER_ROLE_ADMIN, permissions=["accounts", "docs"]
    )
    use_case, _, _ = _make_use_case([admin1, admin2], extra_keys=("docs",))

    # admin1 removes their own accounts permission; admin2 still holds it — allowed
    result = await use_case.update_permissions(
        admin_id=1,
        permissions=["docs"],
        requesting_admin_id=1,
    )

    assert "accounts" not in result.permissions


@pytest.mark.asyncio
async def test_update_permissions_guards_stripping_last_accounts_holder_by_other_admin():
    admin1 = make_user_dto(
        id=1, username="admin1", role=USER_ROLE_ADMIN, permissions=["accounts"]
    )
    admin2 = make_user_dto(
        id=2, username="admin2", role=USER_ROLE_ADMIN, permissions=["docs"]
    )
    use_case, _, _ = _make_use_case([admin1, admin2])

    # admin2 tries to strip admin1's accounts permission; admin1 is the last holder
    with pytest.raises(AdminLastAccountsGuardException):
        await use_case.update_permissions(
            admin_id=1,
            permissions=["docs"],  # no "accounts"
            requesting_admin_id=2,
        )


# ── Tests: change_password ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_raises_on_wrong_current_password():
    admin = make_user_dto(
        id=1,
        username="admin",
        password=hash_password("correct_pass"),
        role=USER_ROLE_ADMIN,
    )
    use_case, _, _ = _make_use_case([admin], auth_user=admin)

    with pytest.raises(InvalidCredentialsException):
        await use_case.change_password(
            user_id=1, current_password="wrong_pass", new_password="NewPass1234!"
        )


@pytest.mark.asyncio
async def test_change_password_revokes_all_tokens_on_success():
    admin = make_user_dto(
        id=1,
        username="admin",
        password=hash_password("correct_pass"),
        role=USER_ROLE_ADMIN,
    )
    use_case, _, auth_service = _make_use_case([admin], auth_user=admin)

    await use_case.change_password(
        user_id=1, current_password="correct_pass", new_password="NewPass1234!"
    )

    assert 1 in auth_service.revoke_calls


@pytest.mark.asyncio
async def test_change_password_updates_password_hash():
    admin = make_user_dto(
        id=1,
        username="admin",
        password=hash_password("old_pass"),
        role=USER_ROLE_ADMIN,
    )
    use_case, repo, _ = _make_use_case([admin], auth_user=admin)

    await use_case.change_password(
        user_id=1, current_password="old_pass", new_password="NewPass1234!"
    )

    updated = repo._store[1]
    assert verify_password("NewPass1234!", updated.password)
    assert not verify_password("old_pass", updated.password)
