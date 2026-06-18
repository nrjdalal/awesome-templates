from datetime import UTC, datetime

from sqlalchemy import delete, select

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database

from ...domain.dtos.link_dto import LinkDTO
from ..database.models.link_model import LinkModel


class LinkRepository(BaseRepository[LinkDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=LinkModel,
            return_entity=LinkDTO,
        )

    async def select_data_by_short_code(self, short_code: str) -> LinkDTO:
        async with self.database.session() as session:
            result = await session.execute(
                select(LinkModel).where(LinkModel.short_code == short_code)
            )
            data = result.scalar_one_or_none()
            if data is None:
                raise BaseCustomException(
                    status_code=404,
                    message=f"Link with short code [ {short_code} ] not found",
                )
            return LinkDTO.model_validate(data, from_attributes=True)

    async def delete_data_by_short_code(self, short_code: str) -> bool:
        async with self.database.session() as session:
            result = await session.execute(
                select(LinkModel).where(LinkModel.short_code == short_code)
            )
            data = result.scalar_one_or_none()
            if data is None:
                raise BaseCustomException(
                    status_code=404,
                    message=f"Link with short code [ {short_code} ] not found",
                )
            await session.delete(data)
            await session.commit()
            return True

    async def delete_expired(self, cutoff: datetime) -> int:
        naive_cutoff = self._to_naive_utc(cutoff)
        async with self.database.session() as session:
            result = await session.execute(
                delete(LinkModel).where(
                    LinkModel.expires_at.is_not(None),
                    LinkModel.expires_at < naive_cutoff,
                )
            )
            await session.commit()
            return result.rowcount or 0

    @staticmethod
    def _to_naive_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
