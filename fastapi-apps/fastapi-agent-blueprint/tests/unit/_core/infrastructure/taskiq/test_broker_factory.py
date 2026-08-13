"""Broker factory tests — both halves of every optional dependency (#351).

The RabbitMQ test used to assert that `create_rabbitmq_broker` raises, without
simulating the package's absence:

    def test_raises_import_error_without_package(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            create_rabbitmq_broker(url="amqp://...")

That passes only while `taskiq-aio-pika` happens to be uninstalled. It became a
real failure once two changes made the installed environment normal: the shipped
image builds with `EXTRAS="--extra sqs --extra rabbitmq"` (#332), and the CI
`typecheck` job installs the same set (#333).

This is the mirror of #330 — there, no test could resolve the *enabled* half of
an optional-infra Selector; here, a test asserted the *disabled* half and was
satisfied by an accident of the environment. Both are "the check does not
actually check".

Absence is now simulated by blocking the import, so each factory is covered on
both sides regardless of what is installed.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util

import pytest
from taskiq import AsyncBroker, InMemoryBroker

from src._core.infrastructure.taskiq.broker import (
    create_rabbitmq_broker,
    create_sqs_broker,
)

_HAS_TASKIQ_AWS = importlib.util.find_spec("taskiq_aws") is not None
_HAS_TASKIQ_AIO_PIKA = importlib.util.find_spec("taskiq_aio_pika") is not None


@pytest.fixture
def block_import(monkeypatch: pytest.MonkeyPatch):
    """Make a named module unimportable for the duration of a test.

    Patches `builtins.__import__` rather than deleting from `sys.modules`: both
    factories import *inside* the function, so the import statement is what has
    to fail. Removing the module from `sys.modules` would only force a re-import
    that then succeeds.
    """

    def _block(module_name: str) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args, **kwargs):
            if name == module_name or name.startswith(f"{module_name}."):
                raise ImportError(f"simulated absence of {module_name}")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

    return _block


class TestCreateSqsBroker:
    @pytest.mark.skipif(not _HAS_TASKIQ_AWS, reason="taskiq-aws not installed")
    def test_creates_async_broker_when_installed(self):
        broker = create_sqs_broker(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/123/test",
            aws_region="ap-northeast-2",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
        )

        assert isinstance(broker, AsyncBroker)

    def test_raises_when_the_package_is_absent(self, block_import):
        block_import("taskiq_aws")

        with pytest.raises(ImportError, match="taskiq-aws"):
            create_sqs_broker(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/123/test",
                aws_region="ap-northeast-2",
            )


class TestCreateRabbitmqBroker:
    @pytest.mark.skipif(
        not _HAS_TASKIQ_AIO_PIKA, reason="taskiq-aio-pika not installed"
    )
    def test_creates_async_broker_when_installed(self):
        broker = create_rabbitmq_broker(url="amqp://guest:guest@localhost:5672/")

        assert isinstance(broker, AsyncBroker)

    def test_raises_when_the_package_is_absent(self, block_import):
        block_import("taskiq_aio_pika")

        with pytest.raises(ImportError, match="taskiq-aio-pika"):
            create_rabbitmq_broker(url="amqp://guest:guest@localhost:5672/")


class TestInMemoryBroker:
    def test_creates_instance(self):
        # No optional dependency — the always-available default.
        assert isinstance(InMemoryBroker(), InMemoryBroker)
