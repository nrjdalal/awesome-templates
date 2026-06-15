from typing import Protocol

from examples.blog.author.domain.dtos.author_dto import AuthorDTO
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol


class AuthorRepositoryProtocol(BaseRepositoryProtocol[AuthorDTO], Protocol):
    pass
