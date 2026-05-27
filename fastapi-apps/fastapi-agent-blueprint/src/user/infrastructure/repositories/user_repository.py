from pydantic import BaseModel
from sqlalchemy import and_, select

from src._core.domain.validation import collect_unique_field_errors
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN, UserDTO
from src.user.domain.exceptions.user_exceptions import UserAlreadyExistsException
from src.user.infrastructure.database.models.user_model import UserModel

_USER_UNIQUE_FIELDS = ("username", "email")


class UserRepository(BaseRepository[UserDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=UserModel,
            return_entity=UserDTO,
        )

    async def insert_data(self, entity: BaseModel) -> UserDTO:
        try:
            return await super().insert_data(entity=entity)
        except DatabaseException as exc:
            await self._raise_user_unique_conflict_if_present(entity, exc)
            raise

    async def insert_datas(self, entities: list[BaseModel]) -> list[UserDTO]:
        try:
            return await super().insert_datas(entities=entities)
        except DatabaseException as exc:
            for entity in entities:
                await self._raise_user_unique_conflict_if_present(entity, exc)
            raise

    async def update_data_by_data_id(self, data_id: int, entity: BaseModel) -> UserDTO:
        try:
            return await super().update_data_by_data_id(data_id=data_id, entity=entity)
        except DatabaseException as exc:
            await self._raise_user_unique_conflict_if_present(
                entity,
                exc,
                exclude_id=data_id,
            )
            raise

    async def select_data_by_username(self, username: str) -> UserDTO | None:
        async with self.database.session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            data = result.scalar_one_or_none()
            if data is None:
                return None
            return UserDTO.model_validate(data, from_attributes=True)

    async def has_real_admin(self) -> bool:
        async with self.database.session() as session:
            result = await session.execute(
                select(UserModel.id)
                .where(
                    and_(
                        UserModel.role == USER_ROLE_ADMIN,
                        UserModel.is_bootstrap_admin.is_(False),
                    )
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def delete_data_by_username(self, username: str) -> bool:
        async with self.database.session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            data = result.scalar_one_or_none()
            if data is None:
                return False
            await session.delete(data)
            await session.commit()
            return True

    async def count_accounts_permission_holders(
        self, exclude_user_id: int | None = None
    ) -> int:
        async with self.database.session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.role == USER_ROLE_ADMIN)
            )
            rows = result.scalars().all()
            return sum(
                1
                for r in rows
                if "accounts" in (r.permissions or [])
                and (exclude_user_id is None or r.id != exclude_user_id)
            )

    async def select_all_admins(self) -> list[UserDTO]:
        async with self.database.session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.role == USER_ROLE_ADMIN)
            )
            rows = result.scalars().all()
            return [UserDTO.model_validate(r, from_attributes=True) for r in rows]

    async def _raise_user_unique_conflict_if_present(
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
            _USER_UNIQUE_FIELDS,
            exclude_id=exclude_id,
        )
        if errors:
            raise UserAlreadyExistsException(errors=errors) from exc
