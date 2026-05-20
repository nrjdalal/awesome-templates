from types import SimpleNamespace

import pytest

from src._core.infrastructure.admin import auth as admin_auth
from src.auth.domain.dtos.auth_dto import AdminSessionDTO
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN, USER_ROLE_USER


class FakeUseCase:
    def __init__(
        self,
        *,
        session: AdminSessionDTO | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.session = session or AdminSessionDTO(
            user_id=1,
            username="admin",
            role=USER_ROLE_ADMIN,
        )
        self.exc = exc
        self.login_requests = []
        self.session_user_ids: list[int] = []

    async def admin_login(self, request):
        self.login_requests.append(request)
        if self.exc:
            raise self.exc
        return self.session

    async def get_admin_session(self, user_id: int) -> AdminSessionDTO:
        self.session_user_ids.append(user_id)
        if self.exc:
            raise self.exc
        return self.session


class FakeNavigate:
    def __init__(self) -> None:
        self.target: str | None = None

    def to(self, target: str) -> None:
        self.target = target


@pytest.fixture
def admin_storage(monkeypatch):
    user_storage: dict = {}
    fake_app = SimpleNamespace(storage=SimpleNamespace(user=user_storage))
    fake_navigate = FakeNavigate()
    fake_ui = SimpleNamespace(navigate=fake_navigate)
    monkeypatch.setattr(admin_auth, "app", fake_app)
    monkeypatch.setattr(admin_auth, "ui", fake_ui)
    monkeypatch.setattr(admin_auth, "_admin_auth_provider", None)
    return user_storage, fake_navigate


@pytest.mark.asyncio
async def test_authenticate_delegates_to_auth_use_case(admin_storage):
    use_case = FakeUseCase()
    provider = admin_auth.AdminAuthProvider(lambda: use_case)

    session = await provider.authenticate("admin", "secret")

    assert session.username == "admin"
    assert use_case.login_requests[0].username == "admin"
    assert use_case.login_requests[0].password == "secret"


@pytest.mark.asyncio
async def test_authenticate_treats_invalid_input_as_invalid_credentials(admin_storage):
    provider = admin_auth.AdminAuthProvider(lambda: FakeUseCase())

    with pytest.raises(InvalidCredentialsException):
        await provider.authenticate("", "")


def test_login_and_logout_store_no_tokens(admin_storage):
    user_storage, _ = admin_storage
    session = AdminSessionDTO(user_id=7, username="root", role=USER_ROLE_ADMIN)

    admin_auth.AdminAuthProvider.login(session)

    assert user_storage == {
        "authenticated": True,
        "user_id": 7,
        "username": "root",
        "role": USER_ROLE_ADMIN,
    }
    assert "access_token" not in user_storage
    assert "refresh_token" not in user_storage

    admin_auth.AdminAuthProvider.logout()

    assert user_storage == {"authenticated": False}


@pytest.mark.asyncio
async def test_require_auth_redirects_when_unauthenticated(admin_storage):
    _, fake_navigate = admin_storage

    assert await admin_auth.require_auth() is False
    assert fake_navigate.target == "/admin/login"


@pytest.mark.asyncio
async def test_require_auth_redirects_for_non_admin_session(admin_storage):
    user_storage, fake_navigate = admin_storage
    user_storage.update(
        {
            "authenticated": True,
            "user_id": 1,
            "username": "user",
            "role": USER_ROLE_USER,
        }
    )

    assert await admin_auth.require_auth() is False
    assert fake_navigate.target == "/admin/login"
    assert user_storage == {"authenticated": False}


@pytest.mark.asyncio
async def test_require_auth_refreshes_admin_session(admin_storage):
    user_storage, fake_navigate = admin_storage
    user_storage.update(
        {
            "authenticated": True,
            "user_id": 1,
            "username": "stale",
            "role": USER_ROLE_ADMIN,
        }
    )
    use_case = FakeUseCase(
        session=AdminSessionDTO(user_id=1, username="fresh", role=USER_ROLE_ADMIN)
    )
    admin_auth.configure_admin_auth_provider(
        admin_auth.AdminAuthProvider(lambda: use_case)
    )

    assert await admin_auth.require_auth() is True
    assert fake_navigate.target is None
    assert user_storage["username"] == "fresh"
    assert use_case.session_user_ids == [1]


@pytest.mark.asyncio
async def test_require_auth_redirects_when_session_refresh_is_denied(admin_storage):
    user_storage, fake_navigate = admin_storage
    user_storage.update(
        {
            "authenticated": True,
            "user_id": 1,
            "username": "stale",
            "role": USER_ROLE_ADMIN,
        }
    )
    use_case = FakeUseCase(exc=InvalidCredentialsException())
    admin_auth.configure_admin_auth_provider(
        admin_auth.AdminAuthProvider(lambda: use_case)
    )

    assert await admin_auth.require_auth() is False
    assert fake_navigate.target == "/admin/login"
    assert user_storage == {"authenticated": False}
