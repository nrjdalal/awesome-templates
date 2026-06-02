"""AdminAuthService unit tests, including the cross-realm trust boundary.

The decisive security property of ADR 049 is that a CUSTOMER-realm token
(minted with the customer secret/issuer/audience) must NOT validate against the
admin realm. ``test_customer_realm_token_is_rejected`` proves that directly at
the service layer.
"""

from __future__ import annotations

import pytest

from src._core.common.jwt_codec import ACCESS_TOKEN_TYPE, JwtCodecConfig, JwtTokenCodec
from src._core.common.security import hash_password
from src.admin_identity.domain.dtos.admin_identity_dto import AdminRefreshTokenDTO
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminInvalidCredentialsException,
    AdminInvalidTokenException,
    AdminRefreshTokenRevokedException,
)
from src.admin_identity.domain.services.admin_auth_service import AdminAuthService
from tests.factories.admin_identity_factory import (
    make_admin_identity_dto,
    make_admin_token_config,
)
from tests.factories.auth_factory import make_auth_token_config


class MockAdminRepository:
    def __init__(self, admins=None) -> None:
        self._admins = {a.id: a for a in (admins or [])}

    async def select_data_by_username(self, username: str):
        for admin in self._admins.values():
            if admin.username == username:
                return admin
        return None

    async def select_data_by_id(self, data_id: int):
        return self._admins[data_id]


class MockAdminRefreshTokenRepository:
    def __init__(self) -> None:
        self._store: dict[str, AdminRefreshTokenDTO] = {}
        self._id = 0

    async def insert_data(self, entity) -> AdminRefreshTokenDTO:
        self._id += 1
        dto = AdminRefreshTokenDTO(
            id=self._id,
            admin_id=entity.admin_id,
            token_hash=entity.token_hash,
            jti=entity.jti,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            created_at=entity.expires_at,
            updated_at=entity.expires_at,
        )
        self._store[entity.jti] = dto
        return dto

    async def select_data_by_jti(self, jti: str):
        return self._store.get(jti)

    async def revoke_by_jti(self, jti: str):
        row = self._store.get(jti)
        if row is None or row.revoked_at is not None:
            return None
        revoked = row.model_copy(update={"revoked_at": row.expires_at})
        self._store[jti] = revoked
        return revoked

    async def revoke_all_by_admin_id(self, admin_id: int) -> int:
        count = 0
        for jti, row in list(self._store.items()):
            if row.admin_id == admin_id and row.revoked_at is None:
                self._store[jti] = row.model_copy(update={"revoked_at": row.expires_at})
                count += 1
        return count


def _service(admins=None) -> AdminAuthService:
    return AdminAuthService(
        admin_refresh_token_repository=MockAdminRefreshTokenRepository(),
        admin_repository=MockAdminRepository(admins),
        token_config=make_admin_token_config(),
    )


@pytest.mark.asyncio
async def test_verify_credentials_returns_admin_on_match():
    admin = make_admin_identity_dto(password=hash_password("secret"))
    service = _service([admin])

    result = await service.verify_credentials(admin.username, "secret")

    assert result.id == admin.id


@pytest.mark.asyncio
async def test_verify_credentials_rejects_wrong_password():
    admin = make_admin_identity_dto(password=hash_password("secret"))
    service = _service([admin])

    with pytest.raises(AdminInvalidCredentialsException):
        await service.verify_credentials(admin.username, "wrong")


@pytest.mark.asyncio
async def test_verify_credentials_rejects_unknown_username():
    service = _service([])

    with pytest.raises(AdminInvalidCredentialsException):
        await service.verify_credentials("ghost", "secret")


@pytest.mark.asyncio
async def test_issue_and_resolve_token_round_trip():
    admin = make_admin_identity_dto(id=7, password=hash_password("secret"))
    service = _service([admin])

    access_token, _refresh = await service.issue_token_pair(admin)
    resolved = await service.get_admin_from_access_token(access_token)

    assert resolved.id == 7


@pytest.mark.asyncio
async def test_rotate_refresh_token_issues_new_pair():
    admin = make_admin_identity_dto(id=7, password=hash_password("secret"))
    service = _service([admin])

    _access, refresh = await service.issue_token_pair(admin)
    new_access, new_refresh = await service.rotate_refresh_token(refresh)

    assert new_access
    assert new_refresh != refresh


@pytest.mark.asyncio
async def test_rotated_refresh_token_cannot_be_reused():
    """A refresh token is single-use: after rotation the old token is revoked."""
    admin = make_admin_identity_dto(id=7, password=hash_password("secret"))
    service = _service([admin])

    _access, refresh = await service.issue_token_pair(admin)
    await service.rotate_refresh_token(refresh)

    with pytest.raises(AdminRefreshTokenRevokedException):
        await service.rotate_refresh_token(refresh)


@pytest.mark.asyncio
async def test_revoke_all_blocks_subsequent_rotation():
    admin = make_admin_identity_dto(id=7, password=hash_password("secret"))
    service = _service([admin])

    _access, refresh = await service.issue_token_pair(admin)
    revoked = await service.revoke_all_tokens_for_admin(7)
    assert revoked == 1

    with pytest.raises(AdminRefreshTokenRevokedException):
        await service.rotate_refresh_token(refresh)


@pytest.mark.asyncio
async def test_customer_realm_token_is_rejected():
    """Trust boundary: a token signed by the CUSTOMER realm (different secret +
    audience) must fail the admin verifier — never resolve to an admin."""
    admin = make_admin_identity_dto(id=5, password=hash_password("secret"))
    service = _service([admin])

    # Mint a token exactly as the customer realm would, with sub=5 (id collision).
    customer_codec = JwtTokenCodec(
        JwtCodecConfig(**make_auth_token_config().model_dump())
    )
    customer_token = customer_codec.encode(subject="5", token_type=ACCESS_TOKEN_TYPE)

    with pytest.raises(AdminInvalidTokenException):
        await service.get_admin_from_access_token(customer_token)
