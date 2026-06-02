from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO


class AdminIdentityRepositoryProtocol(
    BaseRepositoryProtocol[AdminIdentityDTO], Protocol
):
    async def select_data_by_username(
        self, username: str
    ) -> AdminIdentityDTO | None: ...

    async def has_real_admin(self) -> bool:
        """Return True if at least one admin with is_bootstrap_admin=False exists."""
        ...

    async def delete_data_by_username(self, username: str) -> bool: ...

    async def count_accounts_permission_holders(
        self, exclude_admin_id: int | None = None
    ) -> int:
        """Count admins holding the 'accounts' permission key (excluding an id)."""
        ...

    async def select_all_admins(self) -> list[AdminIdentityDTO]:
        """Return all admin identities."""
        ...
