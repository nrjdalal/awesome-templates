from __future__ import annotations

import secrets

import structlog

from src._core.common.security import verify_password
from src._core.infrastructure.admin.permission_registry import AdminPermissionRegistry
from src.auth.domain.exceptions.auth_exceptions import (
    AdminLastAccountsGuardException,
    AdminSelfActionForbiddenException,
    AdminSetupForbiddenException,
    InvalidCredentialsException,
)
from src.auth.domain.services.auth_service import AuthService
from src.user.domain.dtos.user_dto import (
    CreateAdminAccountDTO,
    UserDTO,
)
from src.user.domain.services.user_service import UserService

_logger = structlog.stdlib.get_logger(__name__)


class AdminAccountUseCase:
    """Handles admin account lifecycle: setup, create, delete, permissions, password."""

    def __init__(
        self,
        auth_service: AuthService,
        user_service: UserService,
        permission_registry: AdminPermissionRegistry,
    ) -> None:
        self._auth_service = auth_service
        self._user_service = user_service
        self._permission_registry = permission_registry

    def get_available_permission_keys(self) -> list[str]:
        return self._permission_registry.all_keys()

    # ── Setup (one-time first-admin creation) ──

    async def verify_bootstrap_for_setup(self, username: str, password: str) -> None:
        """Verify bootstrap credentials and confirm setup is still needed.

        Raises AdminSetupForbiddenException when a real admin already exists.
        Raises InvalidCredentialsException when credentials are wrong.
        """
        if await self._user_service.has_real_admin_exists():
            raise AdminSetupForbiddenException()
        user = await self._auth_service.verify_credentials(username, password)
        if not user.is_bootstrap_admin:
            raise AdminSetupForbiddenException()

    async def create_first_admin(
        self,
        username: str,
        full_name: str,
        email: str,
        bootstrap_username: str,
    ) -> tuple[UserDTO, str]:
        """Create the first real admin with all permissions.

        Deletes the bootstrap account immediately after.
        Returns (new_admin_dto, temp_password).
        Raises AdminSetupForbiddenException if a real admin already exists (race guard).
        """
        if await self._user_service.has_real_admin_exists():
            raise AdminSetupForbiddenException()

        temp_password = secrets.token_urlsafe(16)
        all_permissions = self._permission_registry.all_keys()

        new_admin = await self._user_service.create_admin_account(
            CreateAdminAccountDTO(
                username=username,
                full_name=full_name,
                email=email,
                permissions=all_permissions,
            ),
            temp_password=temp_password,
        )

        deleted = await self._user_service.delete_by_username(bootstrap_username)
        if not deleted:
            _logger.warning(
                "admin_bootstrap_user_delete_failed",
                bootstrap_username=bootstrap_username,
                new_admin_id=new_admin.id,
            )

        _logger.info(
            "admin_first_account_created",
            user_id=new_admin.id,
            username=new_admin.username,
        )
        return new_admin, temp_password

    # ── Account management ──

    async def list_admin_accounts(self) -> list[UserDTO]:
        return await self._user_service.select_all_admins()

    async def create_account(self, dto: CreateAdminAccountDTO) -> tuple[UserDTO, str]:
        """Create a new admin account with a generated temporary password.

        Returns (new_admin_dto, temp_password).
        """
        temp_password = secrets.token_urlsafe(16)
        new_admin = await self._user_service.create_admin_account(
            dto, temp_password=temp_password
        )
        _logger.info(
            "admin_account_created",
            user_id=new_admin.id,
            username=new_admin.username,
        )
        return new_admin, temp_password

    async def delete_account(self, admin_id: int, requesting_admin_id: int) -> None:
        """Delete an admin account.

        Guards: not self-delete, not last-accounts holder.
        """
        if admin_id == requesting_admin_id:
            raise AdminSelfActionForbiddenException()

        remaining = await self._user_service.count_accounts_permission_holders(
            exclude_user_id=admin_id
        )
        if remaining == 0:
            raise AdminLastAccountsGuardException()

        await self._user_service.delete_data_by_data_id(data_id=admin_id)
        _logger.info("admin_account_deleted", user_id=admin_id)

    async def update_permissions(
        self,
        admin_id: int,
        permissions: list[str],
        requesting_admin_id: int,
    ) -> UserDTO:
        """Update an admin's page permissions.

        Guards: not self-lockout (removing own 'accounts' perm), not last-accounts.
        """
        if admin_id == requesting_admin_id and "accounts" not in permissions:
            remaining = await self._user_service.count_accounts_permission_holders(
                exclude_user_id=admin_id
            )
            if remaining == 0:
                raise AdminLastAccountsGuardException()

        if admin_id != requesting_admin_id and "accounts" not in permissions:
            remaining = await self._user_service.count_accounts_permission_holders(
                exclude_user_id=admin_id
            )
            if remaining == 0:
                raise AdminLastAccountsGuardException()

        sanitized = [
            k for k in permissions if self._permission_registry.is_valid_key(k)
        ]
        return await self._user_service.update_admin_permissions(admin_id, sanitized)

    # ── Password change ──

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change an admin's password (voluntary or forced).

        Verifies current password, updates hash, clears password_temporary flag,
        and revokes all active refresh tokens for the user.
        """
        user = await self._auth_service.get_user_by_id(user_id)
        if not verify_password(current_password, user.password):
            raise InvalidCredentialsException()

        await self._user_service.change_admin_password(user_id, new_password)
        revoked = await self._auth_service.revoke_all_tokens_for_user(user_id)
        _logger.info(
            "admin_password_changed",
            user_id=user_id,
            tokens_revoked=revoked,
        )
