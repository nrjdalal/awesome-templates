from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Any

from src._core.common.jwt_codec import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    InvalidTokenError,
    JwtCodecConfig,
    JwtTokenCodec,
    TokenExpiredError,
)
from src._core.common.security import verify_password
from src._core.exceptions.base_exception import BaseCustomException
from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    AdminRefreshTokenCreateDTO,
    AdminRefreshTokenDTO,
    AdminTokenConfig,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminInvalidCredentialsException,
    AdminInvalidTokenException,
    AdminRefreshTokenRevokedException,
    AdminTokenExpiredException,
)
from src.admin_identity.domain.protocols.admin_identity_repository_protocol import (
    AdminIdentityRepositoryProtocol,
)
from src.admin_identity.domain.protocols.admin_refresh_token_repository_protocol import (
    AdminRefreshTokenRepositoryProtocol,
)


class AdminAuthService:
    """Admin-realm authentication — mirrors AuthService but is bound to the
    admin identity store and the SEPARATE admin token realm (distinct secret /
    issuer / audience). Shares the JWT codec mechanism with the customer realm.
    """

    def __init__(
        self,
        admin_refresh_token_repository: AdminRefreshTokenRepositoryProtocol,
        admin_repository: AdminIdentityRepositoryProtocol,
        token_config: AdminTokenConfig,
    ) -> None:
        self._refresh_token_repository = admin_refresh_token_repository
        self._admin_repository = admin_repository
        self._token_config = token_config
        self._codec = JwtTokenCodec(JwtCodecConfig(**token_config.model_dump()))

    async def verify_credentials(
        self, username: str, password: str
    ) -> AdminIdentityDTO:
        admin = await self._admin_repository.select_data_by_username(username)
        if admin is None or not verify_password(password, admin.password):
            raise AdminInvalidCredentialsException()
        return admin

    async def issue_token_pair(self, admin: AdminIdentityDTO) -> tuple[str, str]:
        access_token = self._codec.encode(
            subject=str(admin.id), token_type=ACCESS_TOKEN_TYPE
        )
        refresh_token = self._codec.encode(
            subject=str(admin.id), token_type=REFRESH_TOKEN_TYPE
        )
        payload = self._decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        await self._refresh_token_repository.insert_data(
            AdminRefreshTokenCreateDTO(
                admin_id=admin.id,
                token_hash=self._codec.hash_token(refresh_token),
                jti=str(payload["jti"]),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            )
        )
        return access_token, refresh_token

    async def get_admin_from_access_token(self, token: str) -> AdminIdentityDTO:
        payload = self._decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
        admin_id = self._admin_id_from_payload(payload)
        return await self.get_admin_by_id(admin_id)

    async def get_admin_by_id(self, admin_id: int) -> AdminIdentityDTO:
        try:
            return await self._admin_repository.select_data_by_id(admin_id)
        except BaseCustomException as exc:
            if exc.status_code == 404:
                raise AdminInvalidTokenException() from exc
            raise

    async def rotate_refresh_token(self, token: str) -> tuple[str, str]:
        payload = self._decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
        token_row = await self._load_active_refresh_token(payload, token)
        revoked = await self._refresh_token_repository.revoke_by_jti(token_row.jti)
        if revoked is None:
            raise AdminRefreshTokenRevokedException()
        try:
            admin = await self._admin_repository.select_data_by_id(token_row.admin_id)
        except BaseCustomException as exc:
            if exc.status_code == 404:
                raise AdminInvalidTokenException() from exc
            raise
        return await self.issue_token_pair(admin)

    async def revoke_all_tokens_for_admin(self, admin_id: int) -> int:
        return await self._refresh_token_repository.revoke_all_by_admin_id(admin_id)

    async def revoke_refresh_token(self, token: str) -> bool:
        payload = self._decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
        token_row = await self._refresh_token_repository.select_data_by_jti(
            str(payload["jti"])
        )
        if token_row is None:
            raise AdminInvalidTokenException()
        if not hmac.compare_digest(token_row.token_hash, self._codec.hash_token(token)):
            raise AdminInvalidTokenException()
        if token_row.revoked_at is not None:
            return True
        await self._refresh_token_repository.revoke_by_jti(token_row.jti)
        return True

    async def _load_active_refresh_token(
        self,
        payload: dict[str, Any],
        token: str,
    ) -> AdminRefreshTokenDTO:
        token_row = await self._refresh_token_repository.select_data_by_jti(
            str(payload["jti"])
        )
        if token_row is None:
            raise AdminInvalidTokenException()
        if token_row.revoked_at is not None:
            raise AdminRefreshTokenRevokedException()
        if self._as_utc(token_row.expires_at) <= datetime.now(UTC):
            raise AdminTokenExpiredException()
        if not hmac.compare_digest(token_row.token_hash, self._codec.hash_token(token)):
            raise AdminInvalidTokenException()
        return token_row

    def _decode_token(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            return self._codec.decode(token, expected_type=expected_type)
        except TokenExpiredError as exc:
            raise AdminTokenExpiredException() from exc
        except InvalidTokenError as exc:
            raise AdminInvalidTokenException() from exc

    def _admin_id_from_payload(self, payload: dict[str, Any]) -> int:
        try:
            return int(payload["sub"])
        except (TypeError, ValueError) as exc:
            raise AdminInvalidTokenException() from exc

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
