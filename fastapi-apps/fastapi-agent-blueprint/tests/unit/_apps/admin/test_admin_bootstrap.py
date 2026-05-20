from types import SimpleNamespace

import pytest

from src._apps.admin import bootstrap as admin_bootstrap
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN
from tests.factories.user_factory import make_user_dto


class FakeFastAPI:
    def __init__(self) -> None:
        self.handlers = {}

    def add_event_handler(self, event_type: str, handler) -> None:
        self.handlers[event_type] = handler


class FakeUserService:
    def __init__(self) -> None:
        self.entity = None

    async def ensure_admin_user(self, entity):
        self.entity = entity
        return make_user_dto(
            id=1,
            username=entity.username,
            email=entity.email,
            role=USER_ROLE_ADMIN,
        )


@pytest.mark.asyncio
async def test_install_bootstrap_admin_seed_registers_startup_handler(monkeypatch):
    service = FakeUserService()
    app = FakeFastAPI()
    container = SimpleNamespace(
        user_container=SimpleNamespace(user_service=lambda: service)
    )
    monkeypatch.setattr(
        admin_bootstrap,
        "settings",
        SimpleNamespace(
            admin_bootstrap_enabled=True,
            admin_bootstrap_username="admin",
            admin_bootstrap_password="secret",
            admin_bootstrap_email="admin@example.com",
            admin_bootstrap_full_name="Admin User",
        ),
    )

    admin_bootstrap._install_bootstrap_admin_seed(app, container)
    await app.handlers["startup"]()

    assert service.entity.username == "admin"
    assert service.entity.password == "secret"


def test_install_bootstrap_admin_seed_skips_when_disabled(monkeypatch):
    app = FakeFastAPI()
    container = SimpleNamespace()
    monkeypatch.setattr(
        admin_bootstrap,
        "settings",
        SimpleNamespace(admin_bootstrap_enabled=False),
    )

    admin_bootstrap._install_bootstrap_admin_seed(app, container)

    assert app.handlers == {}
