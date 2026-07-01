from fastapi import FastAPI

from ....infrastructure.di.webhook_receiver_container import (
    WebhookReceiverContainer,
)
from ...worker.tasks import webhook_event_task
from ..routers import webhook_event_router


def create_webhook_receiver_container(
    webhook_receiver_container: WebhookReceiverContainer,
) -> None:
    # Wire the router AND the worker task module. Under the quickstart
    # InMemoryBroker, ``.kiq()`` runs the task inline in THIS (server) process,
    # so the task's ``Provide[...]`` markers must be wired here too — not only in
    # the worker bootstrap (which handles the cross-process RabbitMQ/SQS case).
    webhook_receiver_container.wire(modules=[webhook_event_router, webhook_event_task])


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
