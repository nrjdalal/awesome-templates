"""Classification domain independent bootstrap"""

from fastapi import FastAPI

from src.classification.infrastructure.di.classification_container import (
    ClassificationContainer,
)
from src.classification.interface.server.routers import classification_router


def create_classification_container(
    classification_container: ClassificationContainer,
) -> None:
    classification_container.wire(
        packages=["src.classification.interface.server.routers"]
    )


def setup_classification_routes(app: FastAPI) -> None:
    """Register classification domain routes"""
    app.include_router(
        router=classification_router.router, prefix="/v1", tags=["Classification"]
    )


def bootstrap_classification_domain(
    app: FastAPI,
    classification_container: ClassificationContainer,
) -> None:
    create_classification_container(classification_container=classification_container)
    setup_classification_routes(app=app)
