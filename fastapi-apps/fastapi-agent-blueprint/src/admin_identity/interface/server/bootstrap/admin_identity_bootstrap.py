"""Admin identity domain independent bootstrap."""

from fastapi import FastAPI

from src.admin_identity.infrastructure.di.admin_identity_container import (
    AdminIdentityContainer,
)
from src.admin_identity.interface.server.routers import admin_auth_router


def create_admin_identity_container(
    admin_identity_container: AdminIdentityContainer,
) -> None:
    admin_identity_container.wire(
        packages=[
            "src.admin_identity.interface.server.routers",
            "src.admin_identity.interface.server.dependencies",
        ]
    )


def setup_admin_identity_routes(app: FastAPI) -> None:
    app.include_router(
        router=admin_auth_router.router, prefix="/v1", tags=["Admin Auth"]
    )


def bootstrap_admin_identity_domain(
    app: FastAPI, admin_identity_container: AdminIdentityContainer
) -> None:
    create_admin_identity_container(admin_identity_container=admin_identity_container)
    setup_admin_identity_routes(app=app)
