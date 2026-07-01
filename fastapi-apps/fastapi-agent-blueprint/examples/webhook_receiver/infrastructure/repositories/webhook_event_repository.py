from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database

from ...domain.dtos.webhook_event_dto import WebhookEventDTO
from ..database.models.webhook_event_model import (
    WebhookEventModel,
)


class WebhookEventRepository(BaseRepository[WebhookEventDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=WebhookEventModel,
            return_entity=WebhookEventDTO,
        )
