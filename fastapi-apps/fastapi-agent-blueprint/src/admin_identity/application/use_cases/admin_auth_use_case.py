from __future__ import annotations

from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    AdminSessionDTO,
    AdminTokenConfig,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminCredentialDisabledException,
    AdminInvalidCredentialsException,
    AdminSetupRequiredException,
)
from src.admin_identity.domain.services.admin_auth_service import AdminAuthService
from src.admin_identity.domain.services.admin_identity_service import (
    AdminIdentityService,
)
from src.admin_identity.interface.server.schemas.admin_auth_schema import (
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminRefreshTokenRequest,
    AdminTokenPairData,
)


class AdminAuthUseCase:
    def __init__(
        self,
        admin_auth_service: AdminAuthService,
        admin_identity_service: AdminIdentityService,
        token_config: AdminTokenConfig,
    ) -> None:
        self._admin_auth_service = admin_auth_service
        self._admin_identity_service = admin_identity_service
        self._token_config = token_config

    # ── NiceGUI session flow (token-less, IC-155-1) ──

    async def admin_login(self, request: AdminLoginRequest) -> AdminSessionDTO:
        admin = await self._admin_auth_service.verify_credentials(
            request.username,
            request.password,
        )
        if admin.is_bootstrap_admin:
            if not await self._admin_identity_service.has_real_admin_exists():
                raise AdminSetupRequiredException()
            raise AdminCredentialDisabledException()
        return self._admin_session_for(admin)

    async def get_admin_session(self, admin_id: int) -> AdminSessionDTO:
        admin = await self._admin_auth_service.get_admin_by_id(admin_id)
        return self._admin_session_for(admin)

    # ── HTTP API token flow (admin-realm JWT) ──

    async def login(self, request: AdminLoginRequest) -> AdminTokenPairData:
        admin = await self._admin_auth_service.verify_credentials(
            request.username,
            request.password,
        )
        # Bootstrap and temp-password admins must complete setup / password
        # change via the NiceGUI dashboard before using the token API.
        if admin.is_bootstrap_admin or admin.password_temporary:
            raise AdminInvalidCredentialsException()
        return await self._token_pair_for(admin)

    async def refresh(self, request: AdminRefreshTokenRequest) -> AdminTokenPairData:
        (
            access_token,
            refresh_token,
        ) = await self._admin_auth_service.rotate_refresh_token(request.refresh_token)
        admin = await self._admin_auth_service.get_admin_from_access_token(access_token)
        return self._token_pair(access_token, refresh_token, admin)

    async def logout(self, request: AdminLogoutRequest) -> bool:
        return await self._admin_auth_service.revoke_refresh_token(
            request.refresh_token
        )

    async def get_current_admin(self, token: str) -> AdminIdentityDTO:
        return await self._admin_auth_service.get_admin_from_access_token(token)

    # ── helpers ──

    async def _token_pair_for(self, admin: AdminIdentityDTO) -> AdminTokenPairData:
        access_token, refresh_token = await self._admin_auth_service.issue_token_pair(
            admin
        )
        return self._token_pair(access_token, refresh_token, admin)

    def _token_pair(
        self,
        access_token: str,
        refresh_token: str,
        admin: AdminIdentityDTO,
    ) -> AdminTokenPairData:
        return AdminTokenPairData(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",  # noqa: S106
            expires_in=60 * self._token_config.access_token_minutes,
            admin=admin,
        )

    def _admin_session_for(self, admin: AdminIdentityDTO) -> AdminSessionDTO:
        return AdminSessionDTO(
            user_id=admin.id,
            username=admin.username,
            password_temporary=admin.password_temporary,
            permissions=admin.permissions,
        )
