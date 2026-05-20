"""AI usage domain independent bootstrap."""

from fastapi import FastAPI

from src._core.config import settings
from src.ai_usage.infrastructure.di.ai_usage_container import AiUsageContainer
from src.ai_usage.interface.server.routers import ai_usage_router


def create_ai_usage_container(ai_usage_container: AiUsageContainer) -> None:
    ai_usage_container.wire(packages=["src.ai_usage.interface.server.routers"])


def setup_ai_usage_routes(app: FastAPI) -> None:
    if not settings.ai_usage_public_api_enabled:
        return
    app.include_router(router=ai_usage_router.router, prefix="/v1", tags=["AI Usage"])


def bootstrap_ai_usage_domain(
    app: FastAPI, ai_usage_container: AiUsageContainer
) -> None:
    create_ai_usage_container(ai_usage_container=ai_usage_container)
    setup_ai_usage_routes(app=app)
