from examples.blog.author.domain.dtos.author_dto import AuthorDTO
from examples.blog.author.domain.protocols.author_repository_protocol import (
    AuthorRepositoryProtocol,
)
from examples.blog.author.interface.server.schemas.author_schema import (
    CreateAuthorRequest,
    UpdateAuthorRequest,
)
from src._core.domain.services.base_service import BaseService


class AuthorService(BaseService[CreateAuthorRequest, UpdateAuthorRequest, AuthorDTO]):
    def __init__(self, author_repository: AuthorRepositoryProtocol) -> None:
        super().__init__(repository=author_repository)
