import structlog

from src._core.common.security import hash_password
from src._core.domain.services.base_service import BaseService
from src.user.domain.dtos.user_dto import (
    USER_ROLE_ADMIN,
    BootstrapAdminUserDTO,
    UpdateUserRoleDTO,
    UserDTO,
)
from src.user.domain.protocols.user_repository_protocol import UserRepositoryProtocol
from src.user.domain.validators import (
    ensure_user_unique_for_batch_create,
    ensure_user_unique_for_create,
    ensure_user_unique_for_update,
)
from src.user.interface.server.schemas.user_schema import (
    CreateUserRequest,
    UpdateUserRequest,
)

_logger = structlog.stdlib.get_logger(__name__)


class UserService(BaseService[CreateUserRequest, UpdateUserRequest, UserDTO]):
    def __init__(self, user_repository: UserRepositoryProtocol) -> None:
        super().__init__(repository=user_repository)
        self._user_repository = user_repository

    async def create_data(self, entity: CreateUserRequest) -> UserDTO:
        entity = entity.model_copy(update={"password": hash_password(entity.password)})
        return await super().create_data(entity=entity)

    async def create_datas(self, entities: list[CreateUserRequest]) -> list[UserDTO]:
        hashed_entities = [
            entity.model_copy(update={"password": hash_password(entity.password)})
            for entity in entities
        ]
        return await super().create_datas(entities=hashed_entities)

    async def update_data_by_data_id(
        self, data_id: int, entity: UpdateUserRequest
    ) -> UserDTO:
        if entity.password:
            entity = entity.model_copy(
                update={"password": hash_password(entity.password)}
            )
        return await super().update_data_by_data_id(data_id=data_id, entity=entity)

    async def ensure_admin_user(self, entity: BootstrapAdminUserDTO) -> UserDTO:
        existing = await self._user_repository.select_data_by_username(entity.username)
        if existing is None:
            created = await self.create_data(CreateUserRequest(**entity.model_dump()))
            admin = await self._set_admin_role(created.id)
            _logger.info(
                "admin_bootstrap_user_created",
                user_id=admin.id,
                username=admin.username,
            )
            return admin
        if existing.role == USER_ROLE_ADMIN:
            _logger.info(
                "admin_bootstrap_user_already_admin",
                user_id=existing.id,
                username=existing.username,
            )
            return existing
        admin = await self._set_admin_role(existing.id)
        _logger.info(
            "admin_bootstrap_user_promoted",
            user_id=admin.id,
            username=admin.username,
        )
        return admin

    async def _validate_create(self, entity: CreateUserRequest) -> None:
        await ensure_user_unique_for_create(self._user_repository, entity)

    async def _validate_create_many(self, entities: list[CreateUserRequest]) -> None:
        await ensure_user_unique_for_batch_create(self._user_repository, entities)

    async def _validate_update(
        self,
        data_id: int,
        entity: UpdateUserRequest,
    ) -> None:
        await ensure_user_unique_for_update(self._user_repository, data_id, entity)

    async def _set_admin_role(self, user_id: int) -> UserDTO:
        return await self.repository.update_data_by_data_id(
            data_id=user_id,
            entity=UpdateUserRoleDTO(role=USER_ROLE_ADMIN),
        )
