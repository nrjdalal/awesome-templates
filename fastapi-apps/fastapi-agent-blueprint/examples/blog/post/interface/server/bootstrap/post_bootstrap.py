"""Post domain independent bootstrap"""

from fastapi import FastAPI

from ....infrastructure.di.post_container import PostContainer
from ..routers import post_router


def create_post_container(post_container: PostContainer) -> None:
    # Wire the imported module object (not a package path string) so the
    # Provide markers resolve no matter where the domain package lives
    # (examples/ before the copy, src/ after).
    post_container.wire(modules=[post_router])


def setup_post_routes(app: FastAPI) -> None:
    """Register post domain routes"""
    app.include_router(router=post_router.router, prefix="/v1", tags=["Post"])


def bootstrap_post_domain(app: FastAPI, post_container: PostContainer) -> None:
    create_post_container(post_container=post_container)
    setup_post_routes(app=app)
