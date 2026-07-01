from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.webhook_event_dto import WebhookEventDTO


class WebhookEventRepositoryProtocol(BaseRepositoryProtocol[WebhookEventDTO], Protocol):
    pass
