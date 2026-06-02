from pydantic import BaseModel
from sqlalchemy import select

from src._core.domain.validation import collect_unique_field_errors
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException
from src.user.domain.dtos.user_dto import UserDTO
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
