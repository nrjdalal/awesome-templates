from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src._apps.admin import bootstrap as admin_bootstrap
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO


class FakeFastAPI:
    def __init__(self) -> None:
        self.handlers = {}

    def add_event_handler(self, event_type: str, handler) -> None:
        self.handlers[event_type] = handler


class FakeAdminIdentityService:
    def __init__(self) -> None:
        self.entity = None

    async def ensure_admin_user(self, entity):
        self.entity = entity
        now = datetime.now(UTC)
        return AdminIdentityDTO(
            id=1,
            username=entity.username,
            full_name=entity.full_name,
            email=entity.email,
            password="hashed",  # noqa: S106
            created_at=now,
            updated_at=now,
        )


@pytest.mark.asyncio
async def test_install_bootstrap_admin_seed_registers_startup_handler(monkeypatch):
    service = FakeAdminIdentityService()
    app = FakeFastAPI()
    container = SimpleNamespace(
        admin_identity_container=SimpleNamespace(admin_identity_service=lambda: service)
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
