from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt

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

ACCESS_TOKEN_TYPE = "access"  # noqa: S105
REFRESH_TOKEN_TYPE = "refresh"  # noqa: S105


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
        now = datetime.now(UTC)
        if token_type == ACCESS_TOKEN_TYPE:
            expires_at = now + timedelta(
                minutes=self._token_config.access_token_minutes
            )
        else:
            expires_at = now + timedelta(days=self._token_config.refresh_token_days)
        payload = {
            "sub": str(user.id),
            "jti": uuid4().hex,
            "type": token_type,
            "iat": now,
            "exp": expires_at,
            "iss": self._token_config.issuer,
            "aud": self._token_config.audience,
        }
        return jwt.encode(
            payload,
            self._token_config.secret_key,
            algorithm=self._token_config.algorithm,
        )

    def _decode_token(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._token_config.secret_key,
                algorithms=[self._token_config.algorithm],
                audience=self._token_config.audience,
                issuer=self._token_config.issuer,
                leeway=self._token_config.leeway_seconds,
                options={"require": ["sub", "jti", "type", "iat", "exp", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredException() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenException() from exc

        if payload.get("type") != expected_type:
            raise InvalidTokenException()
        return payload

    def _user_id_from_payload(self, payload: dict[str, Any]) -> int:
        try:
            return int(payload["sub"])
        except (TypeError, ValueError) as exc:
            raise InvalidTokenException() from exc

    def _hash_token(self, token: str) -> str:
        return hmac.new(
            self._token_config.secret_key.encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
