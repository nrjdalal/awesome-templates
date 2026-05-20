"""Auth domain independent bootstrap."""

from fastapi import FastAPI

from src.auth.infrastructure.di.auth_container import AuthContainer
from src.auth.interface.server.routers import auth_router


def create_auth_container(auth_container: AuthContainer) -> None:
    auth_container.wire(
        packages=[
            "src.auth.interface.server.routers",
            "src.auth.interface.server.dependencies",
        ]
    )


def setup_auth_routes(app: FastAPI) -> None:
    app.include_router(router=auth_router.router, prefix="/v1", tags=["Auth"])


def bootstrap_auth_domain(app: FastAPI, auth_container: AuthContainer) -> None:
    create_auth_container(auth_container=auth_container)
    setup_auth_routes(app=app)
