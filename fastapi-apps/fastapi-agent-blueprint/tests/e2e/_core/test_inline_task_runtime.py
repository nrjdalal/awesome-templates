"""The cross-cutting audit task must be wired on the server's inline path.

`bootstrap_task_domains` walks `discover_domains()`, so it covers `src/{domain}/`
tasks only. The audit cleanup task lives under `_apps/worker/tasks/` and is wired
by the worker bootstrap — which a server process never calls. It *is* registered
on the broker the server executes tasks through, so it is dispatchable from here,
and before this was fixed it ran with an unresolved marker:

    AttributeError: 'Provide' object has no attribute 'session'

Found by a post-merge review of #324, not by #324 itself. The domain half of the
same bug was what #324 fixed; this is the piece its own fix did not cover.
"""

from __future__ import annotations

import pytest

# Import order matters: booting the server registers every domain model on
# `Base.metadata`, and `admin_audit_log` carries a foreign key to `user`. Import
# the task module first and collection dies on an unresolvable FK.
from src._apps.server.app import app as _server_app  # noqa: F401
from src._apps.worker.tasks.audit_cleanup_task import audit_cleanup_task


@pytest.mark.asyncio
async def test_the_audit_task_resolves_its_database_marker():
    task = await audit_cleanup_task.kiq()
    result = await task.wait_result(timeout=20)

    rendered = str(result.error) if result.is_err else ""
    assert "'Provide' object" not in rendered, (
        "the audit task ran with an unresolved Provide marker — the server's "
        "inline task runtime wired the domain tasks but not the cross-cutting one"
    )
    assert not result.is_err, (
        f"audit cleanup failed: {type(result.error).__name__}: {rendered}"
    )


@pytest.mark.asyncio
async def test_the_audit_task_is_registered_on_the_broker_the_server_uses():
    """Reachability is the reason the wiring matters. If this task were not
    registered here, the finding above would be theoretical."""
    from src._apps.worker.broker import broker
    from src._core.config import settings

    expected = f"{settings.task_name_prefix}._core.admin.audit_cleanup"
    assert expected in broker.get_all_tasks()
