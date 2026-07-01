from fastapi import FastAPI

from ....infrastructure.di.chatbot_with_memory_container import (
    ChatbotWithMemoryContainer,
)
from ..routers import chatbot_memory_router


def create_chatbot_with_memory_container(
    chatbot_with_memory_container: ChatbotWithMemoryContainer,
) -> None:
    """Wire dependencies into the chatbot-with-memory router package."""
    chatbot_with_memory_container.wire(modules=[chatbot_memory_router])


def setup_chatbot_with_memory_routes(app: FastAPI) -> None:
    """Include chatbot-with-memory routes in the FastAPI app."""
    app.include_router(
        router=chatbot_memory_router.router,
        prefix="/v1",
        tags=["ChatbotWithMemory"],
    )


def bootstrap_chatbot_with_memory_domain(
    app: FastAPI,
    chatbot_with_memory_container: ChatbotWithMemoryContainer,
) -> None:
    """Bootstrap the chatbot-with-memory example domain on the server."""
    create_chatbot_with_memory_container(
        chatbot_with_memory_container=chatbot_with_memory_container
    )
    setup_chatbot_with_memory_routes(app=app)
