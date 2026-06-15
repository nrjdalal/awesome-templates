from examples.webhook_receiver.infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from examples.webhook_receiver.interface.worker.tasks import webhook_event_task


def create_webhook_receiver_container(
    webhook_receiver_container: WebhookReceiverContainer,
) -> None:
    webhook_receiver_container.wire(modules=[webhook_event_task])


def bootstrap_webhook_receiver_domain(
    webhook_receiver_container: WebhookReceiverContainer,
) -> None:
    create_webhook_receiver_container(
        webhook_receiver_container=webhook_receiver_container
    )
