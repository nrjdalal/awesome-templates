from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.user.domain.dtos.user_dto import UserDTO


class UserRepositoryProtocol(BaseRepositoryProtocol[UserDTO], Protocol):
    async def select_data_by_username(self, username: str) -> UserDTO | None: ...

    async def has_real_admin(self) -> bool:
        """Return True if at least one admin with is_bootstrap_admin=False exists."""
        ...

    async def delete_data_by_username(self, username: str) -> bool: ...

    async def count_accounts_permission_holders(
        self, exclude_user_id: int | None = None
    ) -> int:
        """Count admins that hold the 'accounts' permission key (excluding a given user id)."""
        ...

    async def select_all_admins(self) -> list[UserDTO]:
        """Return all users with role=admin."""
        ...
