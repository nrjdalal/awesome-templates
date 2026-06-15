from fastapi import FastAPI

from examples.webhook_receiver.infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from examples.webhook_receiver.interface.server.routers import webhook_event_router


def create_webhook_receiver_container(
    webhook_receiver_container: WebhookReceiverContainer,
) -> None:
    webhook_receiver_container.wire(
        packages=["examples.webhook_receiver.interface.server.routers"]
    )


def setup_webhook_receiver_routes(app: FastAPI) -> None:
    app.include_router(
        router=webhook_event_router.router, prefix="/v1", tags=["WebhookReceiver"]
    )


def bootstrap_webhook_receiver_domain(
    app: FastAPI, webhook_receiver_container: WebhookReceiverContainer
) -> None:
    create_webhook_receiver_container(
        webhook_receiver_container=webhook_receiver_container
    )
    setup_webhook_receiver_routes(app=app)
