"""User domain independent bootstrap"""

from fastapi import FastAPI

from src.user.infrastructure.di.user_container import UserContainer
from src.user.interface.server.routers import user_router


def create_user_container(user_container: UserContainer) -> None:
    user_container.wire(packages=["src.user.interface.server.routers"])


def setup_user_routes(app: FastAPI) -> None:
    """Register user domain routes"""
    app.include_router(router=user_router.router, prefix="/v1", tags=["User"])


def bootstrap_user_domain(app: FastAPI, user_container: UserContainer) -> None:
    create_user_container(user_container=user_container)
    setup_user_routes(app=app)
