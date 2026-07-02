"""Author domain independent bootstrap"""

from fastapi import FastAPI

from ....infrastructure.di.author_container import AuthorContainer
from ..routers import author_router


def create_author_container(author_container: AuthorContainer) -> None:
    # Wire the imported module object (not a package path string) so the
    # Provide markers resolve no matter where the domain package lives
    # (examples/ before the copy, src/ after).
    author_container.wire(modules=[author_router])


def setup_author_routes(app: FastAPI) -> None:
    """Register author domain routes"""
    app.include_router(router=author_router.router, prefix="/v1", tags=["Author"])


def bootstrap_author_domain(app: FastAPI, author_container: AuthorContainer) -> None:
    create_author_container(author_container=author_container)
    setup_author_routes(app=app)
