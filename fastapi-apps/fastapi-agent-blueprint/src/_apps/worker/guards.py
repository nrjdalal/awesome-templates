from taskiq import AsyncBroker, InMemoryBroker


class InMemoryWorkerError(RuntimeError):
    """Raised when a standalone worker is launched on the InMemory broker.

    Taskiq's ``InMemoryBroker`` executes tasks inline in the producer process and
    ``InMemoryBroker.listen()`` raises, so a standalone worker process would
    crash-loop. The launcher fails fast with an actionable message instead.
    """


def ensure_worker_capable_broker(broker: AsyncBroker) -> None:
    """Fail fast when ``broker`` cannot back a standalone worker process.

    Only the inline-only :class:`~taskiq.InMemoryBroker` is rejected; any
    cross-process broker (RabbitMQ, SQS) is accepted.
    """
    if isinstance(broker, InMemoryBroker):
        raise InMemoryWorkerError(
            "BROKER_TYPE=inmemory cannot run a standalone worker: Taskiq's "
            "InMemoryBroker runs tasks inline in the producer process and "
            "InMemoryBroker.listen() raises. Set BROKER_TYPE=rabbitmq or sqs to "
            "run a standalone worker (see docs/canonical-demo.md Step 5)."
        )
