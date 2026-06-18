from datetime import UTC, datetime

from src._core.domain.services.base_service import BaseService

from ...interface.server.schemas.link_schema import (
    CreateLinkRequest,
    UpdateLinkRequest,
)
from ..dtos.link_dto import LinkDTO
from ..protocols.link_repository_protocol import LinkRepositoryProtocol


class LinkService(BaseService[CreateLinkRequest, UpdateLinkRequest, LinkDTO]):
    def __init__(self, link_repository: LinkRepositoryProtocol) -> None:
        self._link_repository = link_repository
        super().__init__(repository=link_repository)

    async def get_by_short_code(self, short_code: str) -> LinkDTO:
        return await self._link_repository.select_data_by_short_code(
            short_code=short_code
        )

    async def delete_by_short_code(self, short_code: str) -> bool:
        return await self._link_repository.delete_data_by_short_code(
            short_code=short_code
        )

    async def delete_expired(self, cutoff: datetime | None = None) -> int:
        cutoff = cutoff or datetime.now(UTC).replace(tzinfo=None)
        return await self._link_repository.delete_expired(cutoff=cutoff)
