from dependency_injector import containers, providers

from src._core.config import settings

from ...domain.services.chatbot_service import ChatService
from ...infrastructure.chatbot.pydantic_ai_chatbot import (
    PydanticAIChatbot,
)
from ...infrastructure.chatbot.stub_chatbot import (
    StubChatbot,
)
from ...infrastructure.repositories.chatbot_repository import (
    ChatbotRepository,
)


def _chatbot_selector() -> str:
    return "real" if settings.llm_model_name else "stub"


class ChatbotWithGuardrailsContainer(containers.DeclarativeContainer):
    """Dependency injection container for the chatbot-with-guardrails example domain."""

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
            guardrails_enabled=settings.guardrails_enabled,
        ),
        stub=providers.Singleton(
            StubChatbot,
            guardrails_enabled=settings.guardrails_enabled,
        ),
    )

    chat_service = providers.Factory(
        ChatService,
        chatbot=chatbot,
        repository=chatbot_repository,
    )
