from src._core.domain.services.base_service import BaseService

from ...interface.server.schemas.author_schema import (
    CreateAuthorRequest,
    UpdateAuthorRequest,
)
from ..dtos.author_dto import AuthorDTO
from ..protocols.author_repository_protocol import (
    AuthorRepositoryProtocol,
)


class AuthorService(BaseService[CreateAuthorRequest, UpdateAuthorRequest, AuthorDTO]):
    def __init__(self, author_repository: AuthorRepositoryProtocol) -> None:
        super().__init__(repository=author_repository)
