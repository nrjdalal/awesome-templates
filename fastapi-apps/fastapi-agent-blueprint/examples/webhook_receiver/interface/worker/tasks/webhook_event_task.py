import asyncio
from datetime import UTC, datetime

import structlog
from dependency_injector.wiring import Provide, inject

from examples.webhook_receiver.domain.services.webhook_event_service import (
    WebhookEventService,
)
from examples.webhook_receiver.infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from examples.webhook_receiver.interface.server.schemas.webhook_event_schema import (
    UpdateWebhookEventRequest,
)
from examples.webhook_receiver.interface.worker.payloads.webhook_event_payload import (
    WEBHOOK_EVENT_TASK_NAME,
    WebhookEventPayload,
)
from src._apps.worker.broker import broker

_logger = structlog.stdlib.get_logger(__name__)


@broker.task(task_name=WEBHOOK_EVENT_TASK_NAME)
@inject
async def process_webhook_task(
    webhook_event_service: WebhookEventService = Provide[
        WebhookReceiverContainer.webhook_event_service
    ],
    **kwargs,
) -> None:
    payload = WebhookEventPayload.model_validate(kwargs)
    event_id = payload.event_id

    _logger.info("webhook_event_processing_started", event_id=event_id)

    # 1. Update status to processing
    await webhook_event_service.update_data_by_data_id(
        data_id=event_id,
        entity=UpdateWebhookEventRequest(status="processing"),
    )

    # 2. Simulate processing (sleep 0.2s)
    await asyncio.sleep(0.2)

    # Fetch fresh event details to log / update
    event = await webhook_event_service.get_data_by_data_id(data_id=event_id)
    summary = f"Processed event {event_id} from source '{event.source}' at {datetime.now(UTC)}"

    # Append summary to payload or just log it
    updated_payload = dict(event.payload)
    updated_payload["processed_summary"] = summary

    # 3. Update status to done + set processed_at
    await webhook_event_service.update_data_by_data_id(
        data_id=event_id,
        entity=UpdateWebhookEventRequest(
            status="done",
            payload=updated_payload,
            processed_at=datetime.now(UTC),
        ),
    )

    _logger.info(
        "webhook_event_processing_completed", event_id=event_id, summary=summary
    )
