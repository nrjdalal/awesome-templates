"""Todo domain independent bootstrap"""

from fastapi import FastAPI

from ....infrastructure.di.todo_container import TodoContainer
from ..routers import todo_router


def create_todo_container(todo_container: TodoContainer) -> None:
    todo_container.wire(modules=[todo_router])


def setup_todo_routes(app: FastAPI) -> None:
    """Register todo domain routes"""
    app.include_router(router=todo_router.router, prefix="/v1", tags=["Todo"])


def bootstrap_todo_domain(app: FastAPI, todo_container: TodoContainer) -> None:
    create_todo_container(todo_container=todo_container)
    setup_todo_routes(app=app)
