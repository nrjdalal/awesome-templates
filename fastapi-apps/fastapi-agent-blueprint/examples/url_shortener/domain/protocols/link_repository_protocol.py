from datetime import datetime
from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.link_dto import LinkDTO


class LinkRepositoryProtocol(BaseRepositoryProtocol[LinkDTO], Protocol):
    async def select_data_by_short_code(self, short_code: str) -> LinkDTO: ...

    async def delete_data_by_short_code(self, short_code: str) -> bool: ...

    async def delete_expired(self, cutoff: datetime) -> int: ...
