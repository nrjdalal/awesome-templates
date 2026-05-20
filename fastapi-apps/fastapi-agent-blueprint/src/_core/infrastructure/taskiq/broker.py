from enum import StrEnum

from taskiq import AsyncBroker


class BrokerType(StrEnum):
    SQS = "sqs"
    RABBITMQ = "rabbitmq"
    INMEMORY = "inmemory"


def create_sqs_broker(
    queue_url: str,
    aws_region: str,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
) -> AsyncBroker:
    """Create an SQS broker via lazy import (optional dependency)."""
    try:
        from collections.abc import Callable
        from typing import TypeVar

        from taskiq.abc.result_backend import AsyncResultBackend
        from taskiq_aws import SQSBroker

        _T = TypeVar("_T")

        class CustomSQSBroker(SQSBroker):
            """Custom SQSBroker that accepts AWS credentials via manual injection.

            The default SQSBroker only loads credentials from environment variables
            or config files. This subclass accepts credentials explicitly in __init__.
            """

            def __init__(
                self,
                queue_url: str,
                aws_region: str,
                aws_access_key_id: str | None = None,
                aws_secret_access_key: str | None = None,
                max_messages: int = 10,
                wait_time: int = 20,
                task_id_generator: Callable[[], str] | None = None,
                result_backend: AsyncResultBackend[_T] | None = None,
            ) -> None:
                super().__init__(
                    queue_url=queue_url,
                    aws_region=aws_region,
                    max_messages=max_messages,
                    wait_time=wait_time,
                    task_id_generator=task_id_generator,
                    result_backend=result_backend,
                )

                if aws_access_key_id and aws_secret_access_key:
                    self.session.set_credentials(
                        access_key=aws_access_key_id,
                        secret_key=aws_secret_access_key,
                    )

    except ImportError:
        raise ImportError(
            "taskiq-aws is required for SQS broker. "
            "Install it with: uv sync --extra sqs"
        )

    return CustomSQSBroker(
        queue_url=queue_url,
        aws_region=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )


def create_rabbitmq_broker(url: str) -> AsyncBroker:
    """Create a RabbitMQ broker via lazy import (optional dependency)."""
    try:
        from taskiq_aio_pika import AioPikaBroker
    except ImportError:
        raise ImportError(
            "taskiq-aio-pika is required for RabbitMQ broker. "
            "Install it with: uv sync --extra rabbitmq"
        )
    return AioPikaBroker(url=url)
