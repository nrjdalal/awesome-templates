import structlog
from pydantic import BaseModel, Field

from src._core.common.security import hash_password
from src._core.domain.services.base_service import BaseService
from src._core.domain.validation import collect_unique_field_errors
from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    BootstrapAdminDTO,
    CreateAdminAccountDTO,
    UpdateAdminPermissionsDTO,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminAlreadyExistsException,
)
from src.admin_identity.domain.protocols.admin_identity_repository_protocol import (
    AdminIdentityRepositoryProtocol,
)


class _BootstrapCreateDTO(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    is_bootstrap_admin: bool = True


class _BootstrapPasswordUpdateDTO(BaseModel):
    password: str


class _AdminAccountCreateDTO(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    permissions: list[str] = Field(default_factory=list)
    password_temporary: bool = True
    is_bootstrap_admin: bool = False


class _PasswordChangeClearTempDTO(BaseModel):
    password: str
    password_temporary: bool = False


_logger = structlog.stdlib.get_logger(__name__)


class AdminIdentityService(
    BaseService[CreateAdminAccountDTO, UpdateAdminPermissionsDTO, AdminIdentityDTO]
):
    def __init__(self, admin_repository: AdminIdentityRepositoryProtocol) -> None:
        super().__init__(repository=admin_repository)
        self._admin_repository = admin_repository

    async def ensure_admin_user(
        self, entity: BootstrapAdminDTO
    ) -> AdminIdentityDTO | None:
        # Once a real admin exists the bootstrap seed must do nothing.
        if await self._admin_repository.has_real_admin():
            _logger.info("admin_bootstrap_seed_skipped_real_admin_exists")
            return None

        existing = await self._admin_repository.select_data_by_username(entity.username)

        if existing is not None and not existing.is_bootstrap_admin:
            # Anti-takeover: the bootstrap username is held by a real admin.
            _logger.critical(
                "admin_bootstrap_username_taken_by_non_bootstrap_user",
                username=entity.username,
                admin_id=existing.id,
            )
            return None

        if existing is not None and existing.is_bootstrap_admin:
            # Recovery: refresh password so the operator can re-enter setup.
            updated = await self._admin_repository.update_data_by_data_id(
                data_id=existing.id,
                entity=_BootstrapPasswordUpdateDTO(
                    password=hash_password(entity.password)
                ),
            )
            _logger.info(
                "admin_bootstrap_password_refreshed",
                admin_id=updated.id,
                username=updated.username,
            )
            return updated

        created = await self._admin_repository.insert_data(
            _BootstrapCreateDTO(
                username=entity.username,
                full_name=entity.full_name,
                email=str(entity.email),
                password=hash_password(entity.password),
            )
        )
        _logger.info(
            "admin_bootstrap_user_created",
            admin_id=created.id,
            username=created.username,
        )
        return created

    async def update_admin_permissions(
        self, admin_id: int, permissions: list[str]
    ) -> AdminIdentityDTO:
        return await self._admin_repository.update_data_by_data_id(
            data_id=admin_id,
            entity=UpdateAdminPermissionsDTO(permissions=permissions),
        )

    async def delete_by_username(self, username: str) -> bool:
        return await self._admin_repository.delete_data_by_username(username)

    async def count_accounts_permission_holders(
        self, exclude_admin_id: int | None = None
    ) -> int:
        return await self._admin_repository.count_accounts_permission_holders(
            exclude_admin_id=exclude_admin_id
        )

    async def has_real_admin_exists(self) -> bool:
        return await self._admin_repository.has_real_admin()

    async def select_all_admins(self) -> list[AdminIdentityDTO]:
        return await self._admin_repository.select_all_admins()

    async def create_admin_account(
        self, dto: CreateAdminAccountDTO, temp_password: str
    ) -> AdminIdentityDTO:
        errors = await collect_unique_field_errors(
            self._admin_repository, dto, ("username", "email")
        )
        if errors:
            raise AdminAlreadyExistsException(errors=errors)
        return await self._admin_repository.insert_data(
            _AdminAccountCreateDTO(
                username=dto.username,
                full_name=dto.full_name,
                email=str(dto.email),
                password=hash_password(temp_password),
                permissions=dto.permissions,
            )
        )

    async def change_admin_password(
        self, admin_id: int, new_password: str
    ) -> AdminIdentityDTO:
        return await self._admin_repository.update_data_by_data_id(
            data_id=admin_id,
            entity=_PasswordChangeClearTempDTO(password=hash_password(new_password)),
        )
