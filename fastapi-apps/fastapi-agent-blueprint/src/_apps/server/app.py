from fastapi import FastAPI

from src._apps.server.bootstrap import bootstrap_app
from src._core.application.dtos.base_response import ErrorResponse
from src._core.config import settings


def create_app():
    app = FastAPI(
        title="FastAPI Agent Blueprint",
        description="AI Agent Backend Platform — MCP server + AI orchestration + async DDD architecture",
        version="1.0.0",
        root_path="/api",
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        responses={
            400: {"model": ErrorResponse, "description": "Bad request"},
            422: {"model": ErrorResponse, "description": "Validation error"},
            401: {
                "model": ErrorResponse,
                "description": "Authentication required or token mismatch",
            },
            403: {"model": ErrorResponse, "description": "Forbidden"},
            404: {"model": ErrorResponse, "description": "Resource not found"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )

    bootstrap_app(app)

    return app


app = create_app()
