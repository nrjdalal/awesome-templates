from examples.webhook_receiver.domain.dtos.webhook_event_dto import WebhookEventDTO
from examples.webhook_receiver.domain.protocols.webhook_event_repository_protocol import (
    WebhookEventRepositoryProtocol,
)
from examples.webhook_receiver.interface.server.schemas.webhook_event_schema import (
    CreateWebhookRequest,
    UpdateWebhookEventRequest,
)
from src._core.domain.services.base_service import BaseService


class WebhookEventService(
    BaseService[CreateWebhookRequest, UpdateWebhookEventRequest, WebhookEventDTO]
):
    def __init__(
        self, webhook_event_repository: WebhookEventRepositoryProtocol
    ) -> None:
        super().__init__(repository=webhook_event_repository)
