from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.post_dto import PostDTO


class PostRepositoryProtocol(BaseRepositoryProtocol[PostDTO], Protocol):
    pass
