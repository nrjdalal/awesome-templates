import pytest

from examples.webhook_receiver.infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from examples.webhook_receiver.interface.server.schemas.webhook_event_schema import (
    CreateWebhookRequest,
)
from examples.webhook_receiver.interface.worker.tasks.webhook_event_task import (
    process_webhook_task,
)


@pytest.mark.anyio
async def test_webhook_event_flow(test_db):
    # Setup Container
    container = WebhookReceiverContainer()
    container.core_container.database.override(test_db)

    # Wire tasks so @inject Provide works
    container.wire(
        modules=[
            "examples.webhook_receiver.interface.worker.tasks.webhook_event_task",
        ]
    )

    # Resolve Service
    service = container.webhook_event_service()

    # 1. Create a pending webhook event
    request = CreateWebhookRequest(
        source="stripe",
        payload={"charge_id": "ch_999", "amount": 1000},
    )
    event = await service.create_data(entity=request)

    # Assert initial state is correct
    assert event.id is not None
    assert event.source == "stripe"
    assert event.status == "pending"
    assert event.processed_at is None
    assert "processed_summary" not in event.payload

    # 2. Trigger worker task using Taskiq's in-memory broker and wait for it to complete
    task = await process_webhook_task.kiq(event_id=event.id)
    await task.wait_result()

    # 3. Retrieve event details after processing
    processed_event = await service.get_data_by_data_id(data_id=event.id)

    # Assert terminal state transitions end at "done"
    assert processed_event.status == "done"
    assert processed_event.processed_at is not None
    assert "processed_summary" in processed_event.payload
    assert "stripe" in processed_event.payload["processed_summary"]

    # Unwire to prevent pollution of container wiring in other tests
    container.unwire()
