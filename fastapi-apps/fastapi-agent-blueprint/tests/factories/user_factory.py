from datetime import datetime

from src.user.domain.dtos.user_dto import USER_ROLE_USER, UserDTO, UserRole
from src.user.interface.server.schemas.user_schema import (
    CreateUserRequest,
    UpdateUserRequest,
)
from src.user.interface.worker.payloads.user_payload import UserTestPayload


def make_user_dto(
    id: int = 1,
    username: str = "testuser",
    full_name: str = "Test User",
    email: str = "test@example.com",
    password: str = "hashed_password",
    role: UserRole = USER_ROLE_USER,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> UserDTO:
    now = datetime.now()
    return UserDTO(
        id=id,
        username=username,
        full_name=full_name,
        email=email,
        password=password,
        role=role,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_create_user_request(
    username: str = "testuser",
    full_name: str = "Test User",
    email: str = "test@example.com",
    password: str = "hashed_password",
) -> CreateUserRequest:
    return CreateUserRequest(
        username=username,
        full_name=full_name,
        email=email,
        password=password,
    )


def make_update_user_request(
    username: str | None = None,
    full_name: str | None = None,
    email: str | None = None,
    password: str | None = None,
) -> UpdateUserRequest:
    return UpdateUserRequest(
        username=username,
        full_name=full_name,
        email=email,
        password=password,
    )


def make_user_test_payload(
    id: int = 1,
    username: str = "testuser",
    full_name: str = "Test User",
    email: str = "test@example.com",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> UserTestPayload:
    now = datetime.now()
    return UserTestPayload(
        id=id,
        username=username,
        full_name=full_name,
        email=email,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )
