from typing import Protocol

from examples.webhook_receiver.domain.dtos.webhook_event_dto import WebhookEventDTO
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol


class WebhookEventRepositoryProtocol(BaseRepositoryProtocol[WebhookEventDTO], Protocol):
    pass
