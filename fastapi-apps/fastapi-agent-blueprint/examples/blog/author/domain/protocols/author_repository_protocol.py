from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.author_dto import AuthorDTO


class AuthorRepositoryProtocol(BaseRepositoryProtocol[AuthorDTO], Protocol):
    pass
