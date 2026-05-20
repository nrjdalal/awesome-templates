import pytest

from src.user.domain.exceptions.user_exceptions import UserAlreadyExistsException
from src.user.infrastructure.repositories.user_repository import UserRepository
from src.user.interface.server.schemas.user_schema import UpdateUserRequest
from tests.factories.user_factory import make_create_user_request


@pytest.mark.asyncio
async def test_insert_and_select(test_db):
    repo = UserRepository(database=test_db)
    request = make_create_user_request(
        username="repo_insert",
        email="repo_insert@example.com",
    )

    created = await repo.insert_data(entity=request)
    assert created.id is not None
    assert created.username == request.username
    assert created.role == "user"

    fetched = await repo.select_data_by_id(data_id=created.id)
    assert fetched.id == created.id
    assert fetched.email == request.email
    assert fetched.role == "user"

    by_username = await repo.select_data_by_username(request.username)
    assert by_username is not None
    assert by_username.id == created.id


@pytest.mark.asyncio
async def test_update(test_db):
    repo = UserRepository(database=test_db)
    created = await repo.insert_data(
        entity=make_create_user_request(
            username="repo_update",
            email="repo_update@example.com",
        )
    )

    updated = await repo.update_data_by_data_id(
        data_id=created.id,
        entity=UpdateUserRequest(full_name="New Name"),
    )
    assert updated.full_name == "New Name"
    assert updated.username == created.username


@pytest.mark.asyncio
async def test_delete(test_db):
    repo = UserRepository(database=test_db)
    created = await repo.insert_data(
        entity=make_create_user_request(
            username="repo_delete",
            email="repo_delete@example.com",
        )
    )

    result = await repo.delete_data_by_data_id(data_id=created.id)
    assert result is True


@pytest.mark.asyncio
async def test_count(test_db):
    repo = UserRepository(database=test_db)
    for i in range(3):
        await repo.insert_data(
            entity=make_create_user_request(
                username=f"countuser{i}",
                email=f"countuser{i}@example.com",
            )
        )

    count = await repo.count_datas()
    assert count >= 3


@pytest.mark.asyncio
async def test_exists_primitives(test_db):
    repo = UserRepository(database=test_db)
    request = make_create_user_request(
        username="repo_exists",
        email="repo_exists@example.com",
    )
    created = await repo.insert_data(entity=request)

    assert await repo.exists_by_id(created.id) is True
    assert await repo.exists_by_id(created.id + 1000) is False
    assert await repo.exists_by_fields({"username": request.username}) is True
    assert (
        await repo.exists_by_fields(
            {"username": request.username},
            exclude_id=created.id,
        )
        is False
    )
    assert await repo.existing_values_by_field(
        "email",
        [request.email, "missing@example.com"],
    ) == {request.email}


@pytest.mark.asyncio
async def test_unique_constraints_reject_duplicate_username_and_email(test_db):
    repo = UserRepository(database=test_db)
    request = make_create_user_request(
        username="repo_unique",
        email="repo_unique@example.com",
    )
    await repo.insert_data(entity=request)

    with pytest.raises(UserAlreadyExistsException) as exc_info:
        await repo.insert_data(entity=request)

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
async def test_unique_constraint_update_conflict_returns_user_exception(test_db):
    repo = UserRepository(database=test_db)
    first = await repo.insert_data(
        entity=make_create_user_request(
            username="repo_upd_one",
            email="repo_unique_update_one@example.com",
        )
    )
    second = await repo.insert_data(
        entity=make_create_user_request(
            username="repo_upd_two",
            email="repo_unique_update_two@example.com",
        )
    )

    with pytest.raises(UserAlreadyExistsException) as exc_info:
        await repo.update_data_by_data_id(
            data_id=second.id,
            entity=UpdateUserRequest(email=first.email),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.details == {
        "errors": [
            {
                "field": "email",
                "message": "email already exists",
                "type": "unique",
            }
        ]
    }
