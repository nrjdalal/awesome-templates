"""SQLite smoke test for the audit log repository (#196).

Exercises the BigInteger→SQLite Integer variant on the autoincrement PK and
verifies that ``Base.metadata.create_all()`` registers the ``admin_audit_log``
table (regression guard for the model-discovery fix).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src._core.infrastructure.admin.audit import (
    AdminAction,
    AdminAuditLogRepository,
    AuditLogDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.models.audit_log_model import AdminAuditLog

# admin_audit_log has a FK → user.id, so the user model must be registered on
# Base.metadata before test_db's create_all() runs. Tests that only import the
# audit package would miss this transitively.
from src.user.infrastructure.database.models.user_model import (  # noqa: F401
    UserModel,
)


@pytest.mark.asyncio
async def test_repository_insert_and_table_registered(test_db):
    repo = AdminAuditLogRepository(test_db)

    dto = AuditLogDTO(
        admin_user_id=42,
        admin_username="alice",
        action=AdminAction.LOGIN,
        domain="auth",
        result=AuditResult.SUCCESS,
        ip_address="192.0.2.10",
        correlation_id="cid-smoke",
    )
    await repo.insert(dto)

    async with test_db.session() as session:
        rows = (await session.execute(select(AdminAuditLog))).scalars().all()

    assert len(rows) >= 1
    inserted = next(r for r in rows if r.correlation_id == "cid-smoke")
    assert inserted.admin_username == "alice"
    assert inserted.action == AdminAction.LOGIN.value
    assert inserted.result == AuditResult.SUCCESS.value
    assert inserted.id is not None  # SQLite autoincrement worked
