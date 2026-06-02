"""Shared JWT encode/decode mechanism.

This is realm-agnostic *machinery* deliberately placed in ``_core`` so that
multiple auth realms (customer auth, admin auth) can reuse the same crypto
primitives while keeping their **trust boundaries** fully separated.

Each realm injects its own :class:`JwtCodecConfig` (distinct secret / issuer /
audience / TTL). Sharing this codec does NOT share the trust boundary — a token
minted for one realm's audience fails ``decode`` in another realm because the
audience/issuer/secret differ. See ADR 049.

The codec raises codec-local exceptions (:class:`TokenExpiredError` /
:class:`InvalidTokenError`); callers translate them into their own
domain-specific exceptions.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt

ACCESS_TOKEN_TYPE = "access"  # noqa: S105
REFRESH_TOKEN_TYPE = "refresh"  # noqa: S105

# Canonical JWT claim shape (IC-153-4). Binding across every realm.
REQUIRED_CLAIMS = ["sub", "jti", "type", "iat", "exp", "iss", "aud"]


class JwtCodecError(Exception):
    """Base class for codec-local token errors."""


class TokenExpiredError(JwtCodecError):
    """The token's signature was valid but it has expired."""


class InvalidTokenError(JwtCodecError):
    """The token is malformed, mis-signed, or fails claim validation."""


@dataclass(frozen=True)
class JwtCodecConfig:
    secret_key: str
    algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    issuer: str
    audience: str
    leeway_seconds: int


class JwtTokenCodec:
    """Encodes/decodes JWTs and derives HMAC token hashes for a single realm."""

    def __init__(self, config: JwtCodecConfig) -> None:
        self._config = config

    def encode(self, *, subject: str, token_type: str) -> str:
        now = datetime.now(UTC)
        if token_type == ACCESS_TOKEN_TYPE:
            expires_at = now + timedelta(minutes=self._config.access_token_minutes)
        else:
            expires_at = now + timedelta(days=self._config.refresh_token_days)
        payload = {
            "sub": subject,
            "jti": uuid4().hex,
            "type": token_type,
            "iat": now,
            "exp": expires_at,
            "iss": self._config.issuer,
            "aud": self._config.audience,
        }
        return jwt.encode(
            payload,
            self._config.secret_key,
            algorithm=self._config.algorithm,
        )

    def decode(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._config.secret_key,
                algorithms=[self._config.algorithm],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        if payload.get("type") != expected_type:
            raise InvalidTokenError()
        return payload

    def hash_token(self, token: str) -> str:
        return hmac.new(
            self._config.secret_key.encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()
