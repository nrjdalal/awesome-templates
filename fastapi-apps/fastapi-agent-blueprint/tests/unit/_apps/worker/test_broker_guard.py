from typing import cast

import pytest
from taskiq import AsyncBroker, InMemoryBroker

from src._apps.worker.guards import InMemoryWorkerError, ensure_worker_capable_broker


def test_inmemory_broker_rejected_for_standalone_worker():
    with pytest.raises(InMemoryWorkerError, match="BROKER_TYPE"):
        ensure_worker_capable_broker(InMemoryBroker())


def test_listenable_broker_passes_guard():
    # Any non-InMemory broker is accepted — the guard only blocks the
    # inline-only InMemoryBroker that cannot back a standalone worker.
    ensure_worker_capable_broker(cast(AsyncBroker, object()))
