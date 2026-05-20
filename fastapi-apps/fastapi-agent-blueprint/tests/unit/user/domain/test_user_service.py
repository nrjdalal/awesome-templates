from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel

from src._core.application.dtos.base_response import PaginationInfo
from src._core.common.security import verify_password
from src._core.domain.validation import ValidationFailed
from src.user.domain.dtos.user_dto import (
    USER_ROLE_ADMIN,
    BootstrapAdminUserDTO,
    UserDTO,
)
from src.user.domain.exceptions.user_exceptions import UserAlreadyExistsException
from src.user.domain.services.user_service import UserService
from src.user.interface.server.schemas.user_schema import UpdateUserRequest
from tests.factories.user_factory import make_create_user_request, make_user_dto


class MockUserRepository:
    """Protocol-based Mock — no need to inherit UserRepository"""

    def __init__(self):
        self._store: dict[int, UserDTO] = {}
        self._next_id = 1

    async def insert_data(self, entity: BaseModel) -> UserDTO:
        dto = make_user_dto(id=self._next_id, **entity.model_dump())
        self._store[self._next_id] = dto
        self._next_id += 1
        return dto

    async def insert_datas(self, entities: list[BaseModel]) -> list[UserDTO]:
        return [await self.insert_data(e) for e in entities]

    async def select_datas(self, page: int, page_size: int) -> list[UserDTO]:
        items = list(self._store.values())
        start = (page - 1) * page_size
        return items[start : start + page_size]

    async def select_data_by_id(self, data_id: int) -> UserDTO:
        if data_id not in self._store:
            raise Exception(f"User {data_id} not found")
        return self._store[data_id]

    async def select_data_by_username(self, username: str) -> UserDTO | None:
        for dto in self._store.values():
            if dto.username == username:
                return dto
        return None

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[UserDTO]:
        return [self._store[i] for i in data_ids if i in self._store]

    async def exists_by_id(self, data_id: int) -> bool:
        return data_id in self._store

    async def exists_by_fields(
        self,
        filters: Mapping[str, Any],
        *,
        exclude_id: int | None = None,
    ) -> bool:
        for data_id, dto in self._store.items():
            if exclude_id is not None and data_id == exclude_id:
                continue
            if all(getattr(dto, field) == value for field, value in filters.items()):
                return True
        return False

    async def existing_values_by_field(
        self,
        field: str,
        values: list[Any],
        *,
        exclude_id: int | None = None,
    ) -> set[Any]:
        value_set = set(values)
        return {
            getattr(dto, field)
            for data_id, dto in self._store.items()
            if (exclude_id is None or data_id != exclude_id)
            and getattr(dto, field) in value_set
        }

    async def select_datas_with_count(
        self,
        page: int,
        page_size: int,
        query_filter=None,
    ) -> tuple[list[UserDTO], int]:
        return await self.select_datas(page, page_size), len(self._store)

    async def update_data_by_data_id(self, data_id: int, entity: BaseModel) -> UserDTO:
        dto = self._store[data_id]
        updated = dto.model_copy(
            update={k: v for k, v in entity.model_dump().items() if v is not None}
        )
        self._store[data_id] = updated
        return updated

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        self._store.pop(data_id, None)
        return True

    async def count_datas(self) -> int:
        return len(self._store)


@pytest.fixture
def user_service():
    return UserService(user_repository=MockUserRepository())


@pytest.mark.asyncio
async def test_create_user(user_service):
    request = make_create_user_request()
    result = await user_service.create_data(entity=request)

    assert result.id == 1
    assert result.username == request.username
    assert result.email == request.email
    assert result.role == "user"
    assert verify_password(request.password, result.password)


@pytest.mark.asyncio
async def test_ensure_admin_user_creates_admin_user(user_service):
    result = await user_service.ensure_admin_user(
        BootstrapAdminUserDTO(
            username="admin",
            full_name="Admin User",
            email="admin@example.com",
            password="secret",
        )
    )

    assert result.username == "admin"
    assert result.role == USER_ROLE_ADMIN
    assert verify_password("secret", result.password)


@pytest.mark.asyncio
async def test_ensure_admin_user_promotes_without_overwriting_password(user_service):
    created = await user_service.create_data(
        entity=make_create_user_request(
            username="admin",
            email="admin-promote@example.com",
            password="old-secret",
        )
    )

    result = await user_service.ensure_admin_user(
        BootstrapAdminUserDTO(
            username="admin",
            full_name="Admin User",
            email="admin@example.com",
            password="new-secret",
        )
    )

    assert result.id == created.id
    assert result.role == USER_ROLE_ADMIN
    assert verify_password("old-secret", result.password)
    assert not verify_password("new-secret", result.password)


@pytest.mark.asyncio
async def test_get_user_by_id(user_service):
    request = make_create_user_request()
    created = await user_service.create_data(entity=request)

    result = await user_service.get_data_by_data_id(data_id=created.id)
    assert result.id == created.id
    assert result.username == created.username


@pytest.mark.asyncio
async def test_update_user(user_service):
    request = make_create_user_request()
    created = await user_service.create_data(entity=request)

    update_request = UpdateUserRequest(full_name="Updated Name")
    result = await user_service.update_data_by_data_id(
        data_id=created.id, entity=update_request
    )
    assert result.full_name == "Updated Name"
    assert result.username == created.username  # unchanged


@pytest.mark.asyncio
async def test_delete_user(user_service):
    request = make_create_user_request()
    created = await user_service.create_data(entity=request)

    success = await user_service.delete_data_by_data_id(data_id=created.id)
    assert success is True

    count = await user_service.count_datas()
    assert count == 0


@pytest.mark.asyncio
async def test_get_datas_returns_pagination(user_service):
    for i in range(3):
        await user_service.create_data(
            entity=make_create_user_request(
                username=f"user{i}",
                email=f"user{i}@example.com",
            )
        )

    datas, pagination = await user_service.get_datas(page=1, page_size=2)

    assert len(datas) == 2
    assert isinstance(pagination, PaginationInfo)
    assert pagination.total_items == 3
    assert pagination.total_pages == 2
    assert pagination.has_next is True
    assert pagination.has_previous is False


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_username_or_email(user_service):
    await user_service.create_data(
        entity=make_create_user_request(
            username="duplicate",
            email="duplicate@example.com",
        )
    )

    with pytest.raises(UserAlreadyExistsException) as exc_info:
        await user_service.create_data(
            entity=make_create_user_request(
                username="duplicate",
                email="duplicate@example.com",
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "USER_ALREADY_EXISTS"
    assert exc_info.value.details == {
        "errors": [
            {
                "field": "username",
                "message": "username already exists",
                "type": "unique",
            },
            {
                "field": "email",
                "message": "email already exists",
                "type": "unique",
            },
        ]
    }


@pytest.mark.asyncio
async def test_update_user_allows_own_unique_values(user_service):
    created = await user_service.create_data(
        entity=make_create_user_request(
            username="selfuser",
            email="self@example.com",
        )
    )

    result = await user_service.update_data_by_data_id(
        data_id=created.id,
        entity=UpdateUserRequest(email="self@example.com"),
    )

    assert result.email == "self@example.com"


@pytest.mark.asyncio
async def test_update_user_rejects_another_users_email(user_service):
    first = await user_service.create_data(
        entity=make_create_user_request(
            username="firstuser",
            email="first@example.com",
        )
    )
    second = await user_service.create_data(
        entity=make_create_user_request(
            username="seconduser",
            email="second@example.com",
        )
    )

    with pytest.raises(UserAlreadyExistsException):
        await user_service.update_data_by_data_id(
            data_id=second.id,
            entity=UpdateUserRequest(email=first.email),
        )


@pytest.mark.asyncio
async def test_create_users_rejects_payload_duplicates_without_insert(user_service):
    with pytest.raises(ValidationFailed) as exc_info:
        await user_service.create_datas(
            [
                make_create_user_request(
                    username="batchdup",
                    email="batch-one@example.com",
                ),
                make_create_user_request(
                    username="batchdup",
                    email="batch-two@example.com",
                ),
            ]
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.details == {
        "errors": [
            {
                "field": "username",
                "message": "Duplicate username in request payload",
                "type": "duplicate",
            }
        ]
    }
    assert await user_service.count_datas() == 0


@pytest.mark.asyncio
async def test_create_users_hashes_passwords(user_service):
    requests = [
        make_create_user_request(
            username="batchuser1",
            email="batchuser1@example.com",
            password="plain-one",
        ),
        make_create_user_request(
            username="batchuser2",
            email="batchuser2@example.com",
            password="plain-two",
        ),
    ]

    results = await user_service.create_datas(entities=requests)

    assert verify_password("plain-one", results[0].password)
    assert verify_password("plain-two", results[1].password)
