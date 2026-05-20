from datetime import UTC, datetime

from sqlalchemy import select

from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src.auth.domain.dtos.auth_dto import RefreshTokenDTO
from src.auth.infrastructure.database.models.refresh_token_model import (
    RefreshTokenModel,
)


class RefreshTokenRepository(BaseRepository[RefreshTokenDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=RefreshTokenModel,
            return_entity=RefreshTokenDTO,
        )

    async def select_data_by_jti(self, jti: str) -> RefreshTokenDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(RefreshTokenModel).where(RefreshTokenModel.jti == jti)
            )
            data = result.scalar_one_or_none()
            if data is None:
                return None
            return RefreshTokenDTO.model_validate(data, from_attributes=True)

    async def revoke_by_jti(self, jti: str) -> RefreshTokenDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(RefreshTokenModel)
                .where(RefreshTokenModel.jti == jti)
                .with_for_update()
            )
            data = result.scalar_one_or_none()
            if data is None or data.revoked_at is not None:
                return None
            data.revoked_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(data)
            return RefreshTokenDTO.model_validate(data, from_attributes=True)
