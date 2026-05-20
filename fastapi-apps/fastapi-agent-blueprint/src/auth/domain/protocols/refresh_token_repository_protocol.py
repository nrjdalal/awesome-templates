from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.auth.domain.dtos.auth_dto import RefreshTokenDTO


class RefreshTokenRepositoryProtocol(BaseRepositoryProtocol[RefreshTokenDTO], Protocol):
    async def select_data_by_jti(self, jti: str) -> RefreshTokenDTO | None: ...

    async def revoke_by_jti(self, jti: str) -> RefreshTokenDTO | None: ...
