from src._core.domain.services.base_service import BaseService

from ...interface.server.schemas.webhook_event_schema import (
    CreateWebhookRequest,
    UpdateWebhookEventRequest,
)
from ..dtos.webhook_event_dto import WebhookEventDTO
from ..protocols.webhook_event_repository_protocol import (
    WebhookEventRepositoryProtocol,
)


class WebhookEventService(
    BaseService[CreateWebhookRequest, UpdateWebhookEventRequest, WebhookEventDTO]
):
    def __init__(
        self, webhook_event_repository: WebhookEventRepositoryProtocol
    ) -> None:
        super().__init__(repository=webhook_event_repository)
