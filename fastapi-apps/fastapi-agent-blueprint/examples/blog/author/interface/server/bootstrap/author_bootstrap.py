"""Author domain independent bootstrap"""

from fastapi import FastAPI

from examples.blog.author.infrastructure.di.author_container import AuthorContainer
from examples.blog.author.interface.server.routers import author_router


def create_author_container(author_container: AuthorContainer) -> None:
    author_container.wire(packages=["examples.blog.author.interface.server.routers"])


def setup_author_routes(app: FastAPI) -> None:
    """Register author domain routes"""
    app.include_router(router=author_router.router, prefix="/v1", tags=["Author"])


def bootstrap_author_domain(app: FastAPI, author_container: AuthorContainer) -> None:
    create_author_container(author_container=author_container)
    setup_author_routes(app=app)
