from typing import Protocol

from src.user.domain.dtos.user_dto import UserDTO
from src.user.interface.server.schemas.user_schema import CreateUserRequest


class UserServiceProtocol(Protocol):
    async def create_data(self, entity: CreateUserRequest) -> UserDTO: ...
