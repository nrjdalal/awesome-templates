from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.user.domain.dtos.user_dto import UserDTO


class UserRepositoryProtocol(BaseRepositoryProtocol[UserDTO], Protocol):
    async def select_data_by_username(self, username: str) -> UserDTO | None: ...
