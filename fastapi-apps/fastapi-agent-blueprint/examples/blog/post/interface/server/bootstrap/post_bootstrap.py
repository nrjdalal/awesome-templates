"""Post domain independent bootstrap"""

from fastapi import FastAPI

from examples.blog.post.infrastructure.di.post_container import PostContainer
from examples.blog.post.interface.server.routers import post_router


def create_post_container(post_container: PostContainer) -> None:
    post_container.wire(packages=["examples.blog.post.interface.server.routers"])


def setup_post_routes(app: FastAPI) -> None:
    """Register post domain routes"""
    app.include_router(router=post_router.router, prefix="/v1", tags=["Post"])


def bootstrap_post_domain(app: FastAPI, post_container: PostContainer) -> None:
    create_post_container(post_container=post_container)
    setup_post_routes(app=app)
