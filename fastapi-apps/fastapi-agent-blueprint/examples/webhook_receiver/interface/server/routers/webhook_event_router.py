from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src._core.application.dtos.base_response import SuccessResponse

from ....domain.services.webhook_event_service import (
    WebhookEventService,
)
from ....infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from ...worker.tasks.webhook_event_task import (
    process_webhook_task,
)
from ..schemas.webhook_event_schema import (
    CreateWebhookRequest,
    WebhookEventResponse,
)

router = APIRouter()


@router.post(
    "/webhook",
    summary="Receive a webhook event",
    response_model=SuccessResponse[WebhookEventResponse],
    response_model_exclude={"pagination"},
)
@inject
async def receive_webhook(
    item: CreateWebhookRequest,
    webhook_event_service: WebhookEventService = Depends(
        Provide[WebhookReceiverContainer.webhook_event_service]
    ),
) -> SuccessResponse[WebhookEventResponse]:
    event = await webhook_event_service.create_data(entity=item)
    await process_webhook_task.kiq(event_id=event.id)
    return SuccessResponse(data=WebhookEventResponse(**event.model_dump()))


@router.get(
    "/webhook/{event_id}",
    summary="Get webhook event by ID",
    response_model=SuccessResponse[WebhookEventResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_webhook(
    event_id: int,
    webhook_event_service: WebhookEventService = Depends(
        Provide[WebhookReceiverContainer.webhook_event_service]
    ),
) -> SuccessResponse[WebhookEventResponse]:
    event = await webhook_event_service.get_data_by_data_id(data_id=event_id)
    return SuccessResponse(data=WebhookEventResponse(**event.model_dump()))
