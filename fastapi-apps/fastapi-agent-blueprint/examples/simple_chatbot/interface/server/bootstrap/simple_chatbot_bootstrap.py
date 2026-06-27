from fastapi import FastAPI

from examples.simple_chatbot.infrastructure.di.simple_chatbot_container import (
    SimpleChatbotContainer,
)
from examples.simple_chatbot.interface.server.routers import chatbot_router


def create_simple_chatbot_container(
    simple_chatbot_container: SimpleChatbotContainer,
) -> None:
    """Wire dependencies into the simple-chatbot router package."""
    simple_chatbot_container.wire(
        packages=["examples.simple_chatbot.interface.server.routers"]
    )


def setup_simple_chatbot_routes(app: FastAPI) -> None:
    """Include simple-chatbot routes in the FastAPI app."""
    app.include_router(
        router=chatbot_router.router, prefix="/v1", tags=["SimpleChatbot"]
    )


def bootstrap_simple_chatbot_domain(
    app: FastAPI, simple_chatbot_container: SimpleChatbotContainer
) -> None:
    """Bootstrap the simple-chatbot example domain on the server."""
    create_simple_chatbot_container(simple_chatbot_container=simple_chatbot_container)
    setup_simple_chatbot_routes(app=app)
