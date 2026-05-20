from datetime import UTC, datetime, timedelta

import pytest

from src.auth.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.user.infrastructure.repositories.user_repository import UserRepository
from tests.factories.auth_factory import make_refresh_token_create_dto
from tests.factories.user_factory import make_create_user_request


@pytest.mark.asyncio
async def test_insert_select_and_revoke_refresh_token(test_db):
    user_repo = UserRepository(database=test_db)
    refresh_repo = RefreshTokenRepository(database=test_db)
    user = await user_repo.insert_data(
        make_create_user_request(
            username="auth_repo_user",
            email="auth_repo_user@example.com",
        )
    )

    created = await refresh_repo.insert_data(
        make_refresh_token_create_dto(
            user_id=user.id,
            token_hash="a" * 64,
            jti="repo-jti",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )

    assert created.id is not None
    fetched = await refresh_repo.select_data_by_jti("repo-jti")
    assert fetched is not None
    assert fetched.user_id == user.id
    revoked = await refresh_repo.revoke_by_jti("repo-jti")
    assert revoked is not None
    assert revoked.revoked_at is not None
    assert await refresh_repo.revoke_by_jti("repo-jti") is None
