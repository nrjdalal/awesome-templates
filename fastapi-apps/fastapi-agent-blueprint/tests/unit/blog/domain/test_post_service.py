from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from examples.blog.author.domain.dtos.author_dto import AuthorDTO
from examples.blog.author.domain.protocols.author_repository_protocol import (
    AuthorRepositoryProtocol,
)
from examples.blog.post.domain.protocols.post_repository_protocol import (
    PostRepositoryProtocol,
)
from examples.blog.post.domain.services.post_service import PostService
from examples.blog.post.interface.server.schemas.post_schema import CreatePostRequest
from src._core.domain.validation import ValidationFailed


def make_author_dto(**kwargs):
    defaults = {
        "id": 1,
        "display_name": "Alice",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return AuthorDTO(**defaults)


def make_service(author_repo=None, post_repo=None):
    return PostService(
        post_repository=post_repo or AsyncMock(spec=PostRepositoryProtocol),
        author_repository=author_repo or AsyncMock(spec=AuthorRepositoryProtocol),
    )


@pytest.mark.asyncio
async def test_get_author_display_name():
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    author_repo.select_datas_by_ids.return_value = [
        make_author_dto(display_name="Alice")
    ]
    service = make_service(author_repo=author_repo)

    name = await service.get_author_display_name(author_id=1)

    assert name == "Alice"
    author_repo.select_datas_by_ids.assert_awaited_once_with([1])


@pytest.mark.asyncio
async def test_get_author_display_name_unknown():
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    author_repo.select_datas_by_ids.return_value = []
    service = make_service(author_repo=author_repo)

    name = await service.get_author_display_name(author_id=999)

    assert name == "Unknown"
    author_repo.select_datas_by_ids.assert_awaited_once_with([999])


@pytest.mark.asyncio
async def test_get_author_display_names_batches_and_dedupes():
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    author_repo.select_datas_by_ids.return_value = [
        make_author_dto(id=1, display_name="Alice"),
        make_author_dto(id=2, display_name="Bob"),
    ]
    service = make_service(author_repo=author_repo)

    names = await service.get_author_display_names([1, 2, 1])

    assert names == {1: "Alice", 2: "Bob"}
    author_repo.select_datas_by_ids.assert_awaited_once()
    (called_ids,) = author_repo.select_datas_by_ids.await_args.args
    assert sorted(called_ids) == [1, 2]


@pytest.mark.asyncio
async def test_get_author_display_names_empty_skips_lookup():
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    service = make_service(author_repo=author_repo)

    names = await service.get_author_display_names([])

    assert names == {}
    author_repo.select_datas_by_ids.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_post_validates_author_exists():
    post_repo = AsyncMock(spec=PostRepositoryProtocol)
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    author_repo.exists_by_id.return_value = True
    inserted = AsyncMock()
    post_repo.insert_data.return_value = inserted
    service = make_service(post_repo=post_repo, author_repo=author_repo)
    request = CreatePostRequest(author_id=1, title="Hi", body="Body")

    result = await service.create_data(entity=request)

    assert result is inserted
    author_repo.exists_by_id.assert_awaited_once_with(1)
    post_repo.insert_data.assert_awaited_once_with(entity=request)


@pytest.mark.asyncio
async def test_create_post_rejects_unknown_author():
    post_repo = AsyncMock(spec=PostRepositoryProtocol)
    author_repo = AsyncMock(spec=AuthorRepositoryProtocol)
    author_repo.exists_by_id.return_value = False
    service = make_service(post_repo=post_repo, author_repo=author_repo)
    request = CreatePostRequest(author_id=999, title="Hi", body="Body")

    with pytest.raises(ValidationFailed) as exc:
        await service.create_data(entity=request)

    assert any(err.field == "author_id" for err in exc.value.errors)
    post_repo.insert_data.assert_not_awaited()
