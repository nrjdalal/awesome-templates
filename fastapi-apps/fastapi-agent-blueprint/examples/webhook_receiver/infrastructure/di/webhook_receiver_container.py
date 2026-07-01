from dependency_injector import containers, providers

from ...domain.services.webhook_event_service import (
    WebhookEventService,
)
from ..repositories.webhook_event_repository import (
    WebhookEventRepository,
)


class WebhookReceiverContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    webhook_event_repository = providers.Singleton(
        WebhookEventRepository,
        database=core_container.database,
    )

    webhook_event_service = providers.Factory(
        WebhookEventService,
        webhook_event_repository=webhook_event_repository,
    )
