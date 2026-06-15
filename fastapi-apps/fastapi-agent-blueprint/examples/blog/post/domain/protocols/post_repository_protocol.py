from typing import Protocol

from examples.blog.post.domain.dtos.post_dto import PostDTO
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol


class PostRepositoryProtocol(BaseRepositoryProtocol[PostDTO], Protocol):
    pass
