# Cross-domain dependency on the author domain. `src.author.*` is the layout
# this example runs in after `cp -r examples/blog/author src/author` — the same
# absolute-import pattern the real `src/auth -> src/user` dependency uses. It
# does not resolve while the file still lives under examples/; the blog unit
# tests provide a src-layout shadow via tests/unit/blog/conftest.py.
from src.author.domain.protocols.author_repository_protocol import (
    AuthorRepositoryProtocol,
)

from src._core.domain.services.base_service import BaseService
from src._core.domain.validation import ensure_existing_references

from ...interface.server.schemas.post_schema import (
    CreatePostRequest,
    UpdatePostRequest,
)
from ..dtos.post_dto import PostDTO
from ..protocols.post_repository_protocol import (
    PostRepositoryProtocol,
)


class PostService(BaseService[CreatePostRequest, UpdatePostRequest, PostDTO]):
    def __init__(
        self,
        post_repository: PostRepositoryProtocol,
        author_repository: AuthorRepositoryProtocol,
    ) -> None:
        super().__init__(repository=post_repository)
        self._author_repository = author_repository

    async def get_author_display_name(self, author_id: int) -> str:
        authors = await self._author_repository.select_datas_by_ids([author_id])
        return authors[0].display_name if authors else "Unknown"

    async def get_author_display_names(self, author_ids: list[int]) -> dict[int, str]:
        if not author_ids:
            return {}
        authors = await self._author_repository.select_datas_by_ids(
            list(set(author_ids))
        )
        return {a.id: a.display_name for a in authors}

    async def _validate_create(self, entity: CreatePostRequest) -> None:
        await ensure_existing_references(
            self._author_repository,
            field="author_id",
            values=[entity.author_id],
            message="Author does not exist",
        )
