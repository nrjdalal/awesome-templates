from fastapi import FastAPI

from ....infrastructure.di.chatbot_with_guardrails_container import (
    ChatbotWithGuardrailsContainer,
)
from ..routers import chatbot_router


def create_chatbot_with_guardrails_container(
    container: ChatbotWithGuardrailsContainer,
) -> None:
    """Wire dependencies into the chatbot-with-guardrails router package."""
    container.wire(modules=[chatbot_router])


def setup_chatbot_with_guardrails_routes(app: FastAPI) -> None:
    """Include chatbot-with-guardrails routes in the FastAPI app."""
    app.include_router(
        router=chatbot_router.router,
        prefix="/v1",
        tags=["ChatbotWithGuardrails"],
    )


def bootstrap_chatbot_with_guardrails_domain(
    app: FastAPI,
    chatbot_with_guardrails_container: ChatbotWithGuardrailsContainer,
) -> None:
    """Bootstrap the chatbot-with-guardrails example domain on the server."""
    create_chatbot_with_guardrails_container(
        container=chatbot_with_guardrails_container
    )
    setup_chatbot_with_guardrails_routes(app=app)
