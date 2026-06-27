from dependency_injector import containers, providers

from examples.simple_chatbot.domain.services.chatbot_service import ChatService
from examples.simple_chatbot.infrastructure.chatbot.pydantic_ai_chatbot import (
    PydanticAIChatbot,
)
from examples.simple_chatbot.infrastructure.chatbot.stub_chatbot import StubChatbot
from examples.simple_chatbot.infrastructure.repositories.chatbot_repository import (
    ChatbotRepository,
)
from src._core.config import settings


def _chatbot_selector() -> str:
    return "real" if settings.llm_model_name else "stub"


class SimpleChatbotContainer(containers.DeclarativeContainer):
    """Dependency injection container for the simple-chatbot example domain."""

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
