from pydantic import BaseModel
from sqlalchemy import select

from src._core.domain.validation import collect_unique_field_errors
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminAlreadyExistsException,
)
from src.admin_identity.infrastructure.database.models.admin_identity_model import (
    AdminIdentityModel,
)

_ADMIN_UNIQUE_FIELDS = ("username", "email")


class AdminIdentityRepository(BaseRepository[AdminIdentityDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=AdminIdentityModel,
            return_entity=AdminIdentityDTO,
        )

    async def insert_data(self, entity: BaseModel) -> AdminIdentityDTO:
        try:
            return await super().insert_data(entity=entity)
        except DatabaseException as exc:
            await self._raise_admin_unique_conflict_if_present(entity, exc)
            raise

    async def update_data_by_data_id(
        self, data_id: int, entity: BaseModel
    ) -> AdminIdentityDTO:
        try:
            return await super().update_data_by_data_id(data_id=data_id, entity=entity)
        except DatabaseException as exc:
            await self._raise_admin_unique_conflict_if_present(
                entity,
                exc,
                exclude_id=data_id,
            )
            raise

    async def select_data_by_username(self, username: str) -> AdminIdentityDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminIdentityModel).where(
                    AdminIdentityModel.username == username
                )
            )
            data = result.scalar_one_or_none()
            if data is None:
                return None
            return AdminIdentityDTO.model_validate(data, from_attributes=True)

    async def has_real_admin(self) -> bool:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminIdentityModel.id)
                .where(AdminIdentityModel.is_bootstrap_admin.is_(False))
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def delete_data_by_username(self, username: str) -> bool:
        async with self.database.session() as session:
            result = await session.execute(
                select(AdminIdentityModel).where(
                    AdminIdentityModel.username == username
                )
            )
            data = result.scalar_one_or_none()
            if data is None:
                return False
            await session.delete(data)
            await session.commit()
            return True

    async def count_accounts_permission_holders(
        self, exclude_admin_id: int | None = None
    ) -> int:
        async with self.database.session() as session:
            result = await session.execute(select(AdminIdentityModel))
            rows = result.scalars().all()
            return sum(
                1
                for r in rows
                if "accounts" in (r.permissions or [])
                and (exclude_admin_id is None or r.id != exclude_admin_id)
            )

    async def select_all_admins(self) -> list[AdminIdentityDTO]:
        async with self.database.session() as session:
            result = await session.execute(select(AdminIdentityModel))
            rows = result.scalars().all()
            return [
                AdminIdentityDTO.model_validate(r, from_attributes=True) for r in rows
            ]

    async def _raise_admin_unique_conflict_if_present(
        self,
        entity: BaseModel,
        exc: DatabaseException,
        *,
        exclude_id: int | None = None,
    ) -> None:
        if exc.error_code != "DB_INTEGRITY_ERROR":
            return
        errors = await collect_unique_field_errors(
            self,
            entity,
            _ADMIN_UNIQUE_FIELDS,
            exclude_id=exclude_id,
        )
        if errors:
            raise AdminAlreadyExistsException(errors=errors) from exc
