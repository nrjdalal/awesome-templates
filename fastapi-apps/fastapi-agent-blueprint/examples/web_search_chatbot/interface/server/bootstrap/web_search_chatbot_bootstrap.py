from fastapi import FastAPI

from ....infrastructure.di.web_search_chatbot_container import (
    WebSearchChatbotContainer,
)
from ..routers import chatbot_router


def create_web_search_chatbot_container(
    web_search_chatbot_container: WebSearchChatbotContainer,
) -> None:
    """Wire dependencies into the web-search-chatbot router package."""
    web_search_chatbot_container.wire(modules=[chatbot_router])


def setup_web_search_chatbot_routes(app: FastAPI) -> None:
    """Include web-search-chatbot routes in the FastAPI app."""
    app.include_router(
        router=chatbot_router.router, prefix="/v1", tags=["WebSearchChatbot"]
    )


def bootstrap_web_search_chatbot_domain(
    app: FastAPI, web_search_chatbot_container: WebSearchChatbotContainer
) -> None:
    """Bootstrap the web-search-chatbot example domain on the server."""
    create_web_search_chatbot_container(
        web_search_chatbot_container=web_search_chatbot_container
    )
    setup_web_search_chatbot_routes(app=app)
