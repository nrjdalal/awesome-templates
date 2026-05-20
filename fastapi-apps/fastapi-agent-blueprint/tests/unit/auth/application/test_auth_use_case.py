import pytest

from src._core.common.security import hash_password, verify_password
from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.auth.domain.services.auth_service import AuthService
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN, UserDTO
from tests.factories.auth_factory import (
    make_auth_token_config,
    make_login_request,
    make_register_request,
)
from tests.factories.user_factory import make_user_dto
from tests.unit.auth.domain.test_auth_service import (
    MockRefreshTokenRepository,
    MockUserRepository,
)


class MockUserService:
    def __init__(self) -> None:
        self.created: UserDTO | None = None

    async def create_data(self, entity) -> UserDTO:
        self.created = make_user_dto(
            id=1,
            username=entity.username,
            full_name=entity.full_name,
            email=entity.email,
            password=hash_password(entity.password),
        )
        return self.created


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_tokens():
    user_service = MockUserService()
    refresh_repo = MockRefreshTokenRepository()
    auth_service = AuthService(
        refresh_token_repository=refresh_repo,
        user_repository=MockUserRepository([]),
        token_config=make_auth_token_config(),
    )
    use_case = AuthUseCase(
        auth_service=auth_service,
        user_service=user_service,
        token_config=make_auth_token_config(),
    )

    result = await use_case.register(make_register_request(password="plain"))

    assert result.token_type == "bearer"
    assert result.access_token
    assert result.refresh_token
    assert user_service.created is not None
    assert verify_password("plain", user_service.created.password)


@pytest.mark.asyncio
async def test_login_returns_token_pair_for_existing_user():
    user = make_user_dto(password=hash_password("secret"))
    refresh_repo = MockRefreshTokenRepository()
    auth_service = AuthService(
        refresh_token_repository=refresh_repo,
        user_repository=MockUserRepository([user]),
        token_config=make_auth_token_config(),
    )
    use_case = AuthUseCase(
        auth_service=auth_service,
        user_service=MockUserService(),
        token_config=make_auth_token_config(),
    )

    result = await use_case.login(make_login_request(username=user.username))

    assert result.user.id == user.id
    assert verify_password("secret", user.password)


@pytest.mark.asyncio
async def test_admin_login_returns_session_for_admin_user():
    user = make_user_dto(password=hash_password("secret"), role=USER_ROLE_ADMIN)
    refresh_repo = MockRefreshTokenRepository()
    auth_service = AuthService(
        refresh_token_repository=refresh_repo,
        user_repository=MockUserRepository([user]),
        token_config=make_auth_token_config(),
    )
    use_case = AuthUseCase(
        auth_service=auth_service,
        user_service=MockUserService(),
        token_config=make_auth_token_config(),
    )

    result = await use_case.admin_login(make_login_request(username=user.username))

    assert result.user_id == user.id
    assert result.username == user.username
    assert result.role == USER_ROLE_ADMIN
    assert refresh_repo._store == {}


@pytest.mark.asyncio
async def test_admin_login_rejects_non_admin_user():
    user = make_user_dto(password=hash_password("secret"))
    auth_service = AuthService(
        refresh_token_repository=MockRefreshTokenRepository(),
        user_repository=MockUserRepository([user]),
        token_config=make_auth_token_config(),
    )
    use_case = AuthUseCase(
        auth_service=auth_service,
        user_service=MockUserService(),
        token_config=make_auth_token_config(),
    )

    with pytest.raises(InvalidCredentialsException):
        await use_case.admin_login(make_login_request(username=user.username))


@pytest.mark.asyncio
async def test_admin_login_rejects_wrong_password_for_admin_user():
    user = make_user_dto(password=hash_password("secret"), role=USER_ROLE_ADMIN)
    auth_service = AuthService(
        refresh_token_repository=MockRefreshTokenRepository(),
        user_repository=MockUserRepository([user]),
        token_config=make_auth_token_config(),
    )
    use_case = AuthUseCase(
        auth_service=auth_service,
        user_service=MockUserService(),
        token_config=make_auth_token_config(),
    )

    with pytest.raises(InvalidCredentialsException):
        await use_case.admin_login(
            make_login_request(username=user.username, password="wrong")
        )
