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
from src.auth.domain.dtos.auth_dto import (
    AuthTokenConfig,
    RefreshTokenCreateDTO,
    RefreshTokenDTO,
)
from src.auth.domain.exceptions.auth_exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    RefreshTokenRevokedException,
    TokenExpiredException,
)
from src.auth.domain.protocols.refresh_token_repository_protocol import (
    RefreshTokenRepositoryProtocol,
)
from src.user.domain.dtos.user_dto import UserDTO
from src.user.domain.protocols.user_repository_protocol import UserRepositoryProtocol


class AuthService:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepositoryProtocol,
        user_repository: UserRepositoryProtocol,
        token_config: AuthTokenConfig,
    ) -> None:
        self._refresh_token_repository = refresh_token_repository
        self._user_repository = user_repository
        self._token_config = token_config
        self._codec = JwtTokenCodec(JwtCodecConfig(**token_config.model_dump()))

    async def verify_credentials(self, username: str, password: str) -> UserDTO:
        user = await self._user_repository.select_data_by_username(username)
        if user is None or not verify_password(password, user.password):
            raise InvalidCredentialsException()
        return user

    async def issue_token_pair(self, user: UserDTO) -> tuple[str, str]:
        access_token = self._encode_token(user=user, token_type=ACCESS_TOKEN_TYPE)
        refresh_token = self._encode_token(user=user, token_type=REFRESH_TOKEN_TYPE)
        payload = self._decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        await self._refresh_token_repository.insert_data(
            RefreshTokenCreateDTO(
                user_id=user.id,
                token_hash=self._hash_token(refresh_token),
                jti=str(payload["jti"]),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            )
        )
        return access_token, refresh_token

    async def get_user_from_access_token(self, token: str) -> UserDTO:
        payload = self._decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
        user_id = self._user_id_from_payload(payload)
        return await self.get_user_by_id(user_id)

    async def get_user_by_id(self, user_id: int) -> UserDTO:
        try:
            return await self._user_repository.select_data_by_id(user_id)
        except BaseCustomException as exc:
            if exc.status_code == 404:
                raise InvalidTokenException() from exc
            raise

    async def rotate_refresh_token(self, token: str) -> tuple[str, str]:
        payload = self._decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
        token_row = await self._load_active_refresh_token(payload, token)
        revoked = await self._refresh_token_repository.revoke_by_jti(token_row.jti)
        if revoked is None:
            raise RefreshTokenRevokedException()
        try:
            user = await self._user_repository.select_data_by_id(token_row.user_id)
        except BaseCustomException as exc:
            if exc.status_code == 404:
                raise InvalidTokenException() from exc
            raise
        return await self.issue_token_pair(user)

    async def revoke_all_tokens_for_user(self, user_id: int) -> int:
        return await self._refresh_token_repository.revoke_all_by_user_id(user_id)

    async def revoke_refresh_token(self, token: str) -> bool:
        payload = self._decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
        token_row = await self._refresh_token_repository.select_data_by_jti(
            str(payload["jti"])
        )
        if token_row is None:
            raise InvalidTokenException()
        if not hmac.compare_digest(token_row.token_hash, self._hash_token(token)):
            raise InvalidTokenException()
        if token_row.revoked_at is not None:
            return True
        await self._refresh_token_repository.revoke_by_jti(token_row.jti)
        return True

    async def _load_active_refresh_token(
        self,
        payload: dict[str, Any],
        token: str,
    ) -> RefreshTokenDTO:
        token_row = await self._refresh_token_repository.select_data_by_jti(
            str(payload["jti"])
        )
        if token_row is None:
            raise InvalidTokenException()
        if token_row.revoked_at is not None:
            raise RefreshTokenRevokedException()
        if self._as_utc(token_row.expires_at) <= datetime.now(UTC):
            raise TokenExpiredException()
        if not hmac.compare_digest(token_row.token_hash, self._hash_token(token)):
            raise InvalidTokenException()
        return token_row

    def _encode_token(self, *, user: UserDTO, token_type: str) -> str:
        return self._codec.encode(subject=str(user.id), token_type=token_type)

    def _decode_token(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            return self._codec.decode(token, expected_type=expected_type)
        except TokenExpiredError as exc:
            raise TokenExpiredException() from exc
        except InvalidTokenError as exc:
            raise InvalidTokenException() from exc

    def _user_id_from_payload(self, payload: dict[str, Any]) -> int:
        try:
            return int(payload["sub"])
        except (TypeError, ValueError) as exc:
            raise InvalidTokenException() from exc

    def _hash_token(self, token: str) -> str:
        return self._codec.hash_token(token)

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
