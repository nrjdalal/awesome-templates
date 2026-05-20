from __future__ import annotations

from src._core.domain.validation import (
    collect_duplicate_field_errors,
    collect_existing_unique_field_errors,
    collect_unique_field_errors,
    raise_if_errors,
)
from src.user.domain.exceptions.user_exceptions import UserAlreadyExistsException
from src.user.domain.protocols.user_repository_protocol import UserRepositoryProtocol
from src.user.interface.server.schemas.user_schema import (
    CreateUserRequest,
    UpdateUserRequest,
)

USER_UNIQUE_FIELDS = ("username", "email")


async def ensure_user_unique_for_create(
    repository: UserRepositoryProtocol,
    entity: CreateUserRequest,
) -> None:
    errors = await collect_unique_field_errors(repository, entity, USER_UNIQUE_FIELDS)
    if errors:
        raise UserAlreadyExistsException(errors=errors)


async def ensure_user_unique_for_batch_create(
    repository: UserRepositoryProtocol,
    entities: list[CreateUserRequest],
) -> None:
    payload_errors = collect_duplicate_field_errors(entities, USER_UNIQUE_FIELDS)
    raise_if_errors(payload_errors)

    existing_errors = await collect_existing_unique_field_errors(
        repository,
        entities,
        USER_UNIQUE_FIELDS,
    )
    if existing_errors:
        raise UserAlreadyExistsException(errors=existing_errors)


async def ensure_user_unique_for_update(
    repository: UserRepositoryProtocol,
    data_id: int,
    entity: UpdateUserRequest,
) -> None:
    errors = await collect_unique_field_errors(
        repository,
        entity,
        USER_UNIQUE_FIELDS,
        exclude_id=data_id,
    )
    if errors:
        raise UserAlreadyExistsException(errors=errors)
