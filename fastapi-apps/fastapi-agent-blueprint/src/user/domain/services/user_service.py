import structlog
from pydantic import BaseModel, Field

from src._core.common.security import hash_password
from src._core.domain.services.base_service import BaseService
from src._core.domain.validation import collect_unique_field_errors
from src.user.domain.dtos.user_dto import (
    USER_ROLE_ADMIN,
    BootstrapAdminUserDTO,
    CreateAdminAccountDTO,
    UpdateAdminPermissionsDTO,
    UpdateUserRoleDTO,
    UserDTO,
)
from src.user.domain.exceptions.user_exceptions import UserAlreadyExistsException
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


class _BootstrapCreateDTO(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    role: str = USER_ROLE_ADMIN
    is_bootstrap_admin: bool = True


class _BootstrapPasswordUpdateDTO(BaseModel):
    password: str


class _AdminAccountCreateDTO(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    role: str = USER_ROLE_ADMIN
    permissions: list[str] = Field(default_factory=list)
    password_temporary: bool = True
    is_bootstrap_admin: bool = False


class _PasswordChangeClearTempDTO(BaseModel):
    password: str
    password_temporary: bool = False


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

    async def ensure_admin_user(self, entity: BootstrapAdminUserDTO) -> UserDTO | None:
        # Once a real admin exists the bootstrap seed must do nothing (P0 anti-re-seed).
        if await self._user_repository.has_real_admin():
            _logger.info("admin_bootstrap_seed_skipped_real_admin_exists")
            return None

        existing = await self._user_repository.select_data_by_username(entity.username)

        if existing is not None and not existing.is_bootstrap_admin:
            # Anti-takeover: someone registered the bootstrap username as a real user.
            _logger.critical(
                "admin_bootstrap_username_taken_by_non_bootstrap_user",
                username=entity.username,
                user_id=existing.id,
            )
            return None

        if existing is not None and existing.is_bootstrap_admin:
            # Recovery: bootstrap row already exists — refresh password so the operator
            # can re-enter setup after forgetting the credential.
            updated = await self._user_repository.update_data_by_data_id(
                data_id=existing.id,
                entity=_BootstrapPasswordUpdateDTO(
                    password=hash_password(entity.password)
                ),
            )
            _logger.info(
                "admin_bootstrap_password_refreshed",
                user_id=updated.id,
                username=updated.username,
            )
            return updated

        # Fresh create: insert directly so we can set is_bootstrap_admin=True in one op.
        created = await self._user_repository.insert_data(
            _BootstrapCreateDTO(
                username=entity.username,
                full_name=entity.full_name,
                email=entity.email,
                password=hash_password(entity.password),
            )
        )
        _logger.info(
            "admin_bootstrap_user_created",
            user_id=created.id,
            username=created.username,
        )
        return created

    async def update_admin_permissions(
        self, user_id: int, permissions: list[str]
    ) -> UserDTO:
        return await self._user_repository.update_data_by_data_id(
            data_id=user_id,
            entity=UpdateAdminPermissionsDTO(permissions=permissions),
        )

    async def delete_by_username(self, username: str) -> bool:
        return await self._user_repository.delete_data_by_username(username)

    async def count_accounts_permission_holders(
        self, exclude_user_id: int | None = None
    ) -> int:
        return await self._user_repository.count_accounts_permission_holders(
            exclude_user_id=exclude_user_id
        )

    async def has_real_admin_exists(self) -> bool:
        return await self._user_repository.has_real_admin()

    async def select_all_admins(self) -> list[UserDTO]:
        return await self._user_repository.select_all_admins()

    async def create_admin_account(
        self, dto: CreateAdminAccountDTO, temp_password: str
    ) -> UserDTO:
        errors = await collect_unique_field_errors(
            self._user_repository, dto, ("username", "email")
        )
        if errors:
            raise UserAlreadyExistsException(errors=errors)
        return await self._user_repository.insert_data(
            _AdminAccountCreateDTO(
                username=dto.username,
                full_name=dto.full_name,
                email=str(dto.email),
                password=hash_password(temp_password),
                permissions=dto.permissions,
            )
        )

    async def change_admin_password(self, user_id: int, new_password: str) -> UserDTO:
        return await self._user_repository.update_data_by_data_id(
            data_id=user_id,
            entity=_PasswordChangeClearTempDTO(password=hash_password(new_password)),
        )

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
