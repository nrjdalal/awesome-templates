from dependency_injector import containers, providers

from src._core.config import settings

from ...domain.services.chatbot_service import ChatService
from ..chatbot.pydantic_ai_chatbot import (
    PydanticAIChatbot,
)
from ..chatbot.stub_chatbot import StubChatbot
from ..repositories.chatbot_repository import (
    ChatbotRepository,
)


def _chatbot_selector() -> str:
    return "real" if settings.llm_model_name else "stub"


class WebSearchChatbotContainer(containers.DeclarativeContainer):
    """Dependency injection container for the web-search-chatbot example domain."""

    core_container = providers.DependenciesContainer()

    chatbot_repository = providers.Singleton(
        ChatbotRepository,
        database=core_container.database,
    )

    chatbot = providers.Selector(
        _chatbot_selector,
        real=providers.Singleton(
            PydanticAIChatbot,
            llm_model=core_container.llm_model,
        ),
        stub=providers.Singleton(StubChatbot),
    )

    chat_service = providers.Factory(
        ChatService,
        chatbot=chatbot,
        repository=chatbot_repository,
    )
