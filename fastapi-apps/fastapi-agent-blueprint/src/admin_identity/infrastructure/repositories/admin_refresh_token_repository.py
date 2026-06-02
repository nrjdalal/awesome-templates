from datetime import UTC, datetime

from sqlalchemy import select

from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src.admin_identity.domain.dtos.admin_identity_dto import AdminRefreshTokenDTO
from src.admin_identity.infrastructure.database.models.admin_refresh_token_model import (
    AdminRefreshTokenModel,
)


class AdminRefreshTokenRepository(BaseRepository[AdminRefreshTokenDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=AdminRefreshTokenModel,
            return_entity=AdminRefreshTokenDTO,
        )

    async def select_data_by_jti(self, jti: str) -> AdminRefreshTokenDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminRefreshTokenModel).where(AdminRefreshTokenModel.jti == jti)
            )
            data = result.scalar_one_or_none()
            if data is None:
                return None
            return AdminRefreshTokenDTO.model_validate(data, from_attributes=True)

    async def revoke_all_by_admin_id(self, admin_id: int) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminRefreshTokenModel).where(
                    AdminRefreshTokenModel.admin_id == admin_id,
                    AdminRefreshTokenModel.revoked_at.is_(None),
                )
            )
            rows = result.scalars().all()
            now = datetime.now(UTC)
            for row in rows:
                row.revoked_at = now
            await session.commit()
            return len(rows)

    async def revoke_by_jti(self, jti: str) -> AdminRefreshTokenDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminRefreshTokenModel)
                .where(AdminRefreshTokenModel.jti == jti)
                .with_for_update()
            )
            data = result.scalar_one_or_none()
            if data is None or data.revoked_at is not None:
                return None
            data.revoked_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(data)
            return AdminRefreshTokenDTO.model_validate(data, from_attributes=True)
