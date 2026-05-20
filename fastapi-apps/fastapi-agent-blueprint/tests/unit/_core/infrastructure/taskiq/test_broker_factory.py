import importlib

import pytest
from taskiq import AsyncBroker, InMemoryBroker

from src._core.infrastructure.taskiq.broker import (
    create_rabbitmq_broker,
    create_sqs_broker,
)

_has_taskiq_aws = importlib.util.find_spec("taskiq_aws") is not None


@pytest.mark.skipif(not _has_taskiq_aws, reason="taskiq-aws not installed")
class TestCreateSqsBroker:
    def test_creates_async_broker(self):
        broker = create_sqs_broker(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/123/test",
            aws_region="ap-northeast-2",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )
        assert isinstance(broker, AsyncBroker)


class TestInMemoryBroker:
    def test_creates_instance(self):
        broker = InMemoryBroker()
        assert isinstance(broker, InMemoryBroker)


class TestCreateRabbitmqBroker:
    def test_raises_import_error_without_package(self):
        """RabbitMQ requires taskiq-aio-pika which is an optional dependency."""
        with pytest.raises((ImportError, ModuleNotFoundError)):
            create_rabbitmq_broker(url="amqp://guest:guest@localhost:5672/")
