from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.admin_identity.domain.dtos.admin_identity_dto import AdminRefreshTokenDTO


class AdminRefreshTokenRepositoryProtocol(
    BaseRepositoryProtocol[AdminRefreshTokenDTO], Protocol
):
    async def select_data_by_jti(self, jti: str) -> AdminRefreshTokenDTO | None: ...

    async def revoke_by_jti(self, jti: str) -> AdminRefreshTokenDTO | None: ...

    async def revoke_all_by_admin_id(self, admin_id: int) -> int: ...
