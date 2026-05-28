"""Taskiq scheduler entrypoint (#206 Phase 2).

Runs as a separate process (``make scheduler`` / ``run_scheduler_local.py``)
and reads ``schedule=[{"cron": "..."}]`` labels from registered ``@broker.task``
callables via ``LabelScheduleSource``.

Adding a new scheduled task is two steps:
1. Decorate the task with ``@broker.task(... schedule=[{"cron": "..."}])``.
2. Make sure the task module is imported somewhere on the worker boot path
   (this module imports cross-cutting ones explicitly; domain tasks should be
   imported by their domain worker bootstrap).

Hybrid-friendly: if a deployment chooses NOT to run the scheduler process
(e.g. serverless workers), the same ``@broker.task`` is still enqueueable via
external cron — the schedule label is simply ignored.
"""

from __future__ import annotations

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

# Importing ``worker.app`` triggers ``bootstrap_app(broker)`` so middlewares
# and the cross-cutting task wiring run in the scheduler process too. Without
# it, the scheduler process has an unbootstrapped broker and any direct task
# invocation (e.g. integration tests, manual debugging) would hit unresolved
# ``Provide`` markers.
from src._apps.worker import app as _worker_app  # noqa: F401
from src._apps.worker.broker import broker

# Side-effect imports so the schedule labels of cross-cutting tasks are
# present when ``LabelScheduleSource`` walks the broker's registered tasks.
from src._apps.worker.tasks import audit_cleanup_task as _audit_cleanup  # noqa: F401

scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])
