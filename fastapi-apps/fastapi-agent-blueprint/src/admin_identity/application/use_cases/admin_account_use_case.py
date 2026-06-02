from __future__ import annotations

import secrets

import structlog

from src._core.common.security import verify_password
from src._core.infrastructure.admin.permission_registry import AdminPermissionRegistry
from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    CreateAdminAccountDTO,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminInvalidCredentialsException,
    AdminLastAccountsGuardException,
    AdminSelfActionForbiddenException,
    AdminSetupForbiddenException,
)
from src.admin_identity.domain.services.admin_auth_service import AdminAuthService
from src.admin_identity.domain.services.admin_identity_service import (
    AdminIdentityService,
)

_logger = structlog.stdlib.get_logger(__name__)


class AdminAccountUseCase:
    """Handles admin account lifecycle: setup, create, delete, permissions, password."""

    def __init__(
        self,
        admin_auth_service: AdminAuthService,
        admin_identity_service: AdminIdentityService,
        permission_registry: AdminPermissionRegistry,
    ) -> None:
        self._admin_auth_service = admin_auth_service
        self._admin_identity_service = admin_identity_service
        self._permission_registry = permission_registry

    def get_available_permission_keys(self) -> list[str]:
        return self._permission_registry.all_keys()

    # ── Setup (one-time first-admin creation) ──

    async def verify_bootstrap_for_setup(self, username: str, password: str) -> None:
        """Verify bootstrap credentials and confirm setup is still needed."""
        if await self._admin_identity_service.has_real_admin_exists():
            raise AdminSetupForbiddenException()
        admin = await self._admin_auth_service.verify_credentials(username, password)
        if not admin.is_bootstrap_admin:
            raise AdminSetupForbiddenException()

    async def create_first_admin(
        self,
        username: str,
        full_name: str,
        email: str,
        bootstrap_username: str,
    ) -> tuple[AdminIdentityDTO, str]:
        """Create the first real admin with all permissions, then delete bootstrap."""
        if await self._admin_identity_service.has_real_admin_exists():
            raise AdminSetupForbiddenException()

        temp_password = secrets.token_urlsafe(16)
        all_permissions = self._permission_registry.all_keys()

        new_admin = await self._admin_identity_service.create_admin_account(
            CreateAdminAccountDTO(
                username=username,
                full_name=full_name,
                email=email,
                permissions=all_permissions,
            ),
            temp_password=temp_password,
        )

        deleted = await self._admin_identity_service.delete_by_username(
            bootstrap_username
        )
        if not deleted:
            _logger.warning(
                "admin_bootstrap_user_delete_failed",
                bootstrap_username=bootstrap_username,
                new_admin_id=new_admin.id,
            )

        _logger.info(
            "admin_first_account_created",
            admin_id=new_admin.id,
            username=new_admin.username,
        )
        return new_admin, temp_password

    # ── Account management ──

    async def list_admin_accounts(self) -> list[AdminIdentityDTO]:
        return await self._admin_identity_service.select_all_admins()

    async def create_account(
        self, dto: CreateAdminAccountDTO
    ) -> tuple[AdminIdentityDTO, str]:
        temp_password = secrets.token_urlsafe(16)
        new_admin = await self._admin_identity_service.create_admin_account(
            dto, temp_password=temp_password
        )
        _logger.info(
            "admin_account_created",
            admin_id=new_admin.id,
            username=new_admin.username,
        )
        return new_admin, temp_password

    async def delete_account(self, admin_id: int, requesting_admin_id: int) -> None:
        if admin_id == requesting_admin_id:
            raise AdminSelfActionForbiddenException()

        remaining = (
            await self._admin_identity_service.count_accounts_permission_holders(
                exclude_admin_id=admin_id
            )
        )
        if remaining == 0:
            raise AdminLastAccountsGuardException()

        await self._admin_identity_service.delete_data_by_data_id(data_id=admin_id)
        _logger.info("admin_account_deleted", admin_id=admin_id)

    async def update_permissions(
        self,
        admin_id: int,
        permissions: list[str],
        requesting_admin_id: int,
    ) -> AdminIdentityDTO:
        if "accounts" not in permissions:
            remaining = (
                await self._admin_identity_service.count_accounts_permission_holders(
                    exclude_admin_id=admin_id
                )
            )
            if remaining == 0:
                raise AdminLastAccountsGuardException()

        sanitized = [
            k for k in permissions if self._permission_registry.is_valid_key(k)
        ]
        return await self._admin_identity_service.update_admin_permissions(
            admin_id, sanitized
        )

    # ── Password change ──

    async def change_password(
        self,
        admin_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change an admin's password, clear the temp flag, revoke refresh tokens."""
        admin = await self._admin_auth_service.get_admin_by_id(admin_id)
        if not verify_password(current_password, admin.password):
            raise AdminInvalidCredentialsException()

        await self._admin_identity_service.change_admin_password(admin_id, new_password)
        revoked = await self._admin_auth_service.revoke_all_tokens_for_admin(admin_id)
        _logger.info(
            "admin_password_changed",
            admin_id=admin_id,
            tokens_revoked=revoked,
        )
