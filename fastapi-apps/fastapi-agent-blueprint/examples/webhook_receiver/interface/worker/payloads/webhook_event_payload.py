from src._core.application.dtos.base_payload import BasePayload
from src._core.config import settings

WEBHOOK_EVENT_TASK_NAME = f"{settings.task_name_prefix}.webhook_receiver.process_event"


class WebhookEventPayload(BasePayload):
    event_id: int
