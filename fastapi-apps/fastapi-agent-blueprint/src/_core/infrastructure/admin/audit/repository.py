"""Append-only repository for the admin audit log.

Phase 1 (#196 PR #205) shipped ``insert``. Phase 2 (#206) adds the query
surface used by ``/admin/audit-log`` and the cleanup task: ``list_filtered``
(summary projection + total), ``get_by_id`` (full row with JSON state for the
detail dialog), and ``delete_older_than`` (retention cleanup).
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AdminAction,
    AuditLogDTO,
    AuditLogFilter,
    AuditLogSummaryDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.models.audit_log_model import AdminAuditLog
from src._core.infrastructure.persistence.rdb.database import Database

_UTC = UTC


class AdminAuditLogRepository:
    """Append-only audit-log repository.

    Deliberately not a ``BaseRepository`` subclass: an audit log is append-only
    plus retention cleanup, not a generic CRUD entity.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    # ── Write ────────────────────────────────────────────────────────────────

    async def insert(self, dto: AuditLogDTO) -> None:
        """Persist a single audit-log entry.

        Raises whatever the database raises — the caller (``AuditLogger.log``)
        is responsible for swallowing/logging any failure so an audit-write
        error never breaks the user action it tried to record.
        """
        model = AdminAuditLog(
            admin_user_id=dto.admin_user_id,
            admin_username=dto.admin_username,
            action=dto.action.value,
            domain=dto.domain,
            record_id=dto.record_id,
            before_state=dto.before_state,
            after_state=dto.after_state,
            result=dto.result.value,
            failure_reason=dto.failure_reason,
            ip_address=dto.ip_address,
            correlation_id=dto.correlation_id,
        )
        async with self._database.session() as session:
            session.add(model)
            await session.commit()

    # ── Read (Phase 2 / #206) ───────────────────────────────────────────────

    # Summary projection: every column EXCEPT ``before_state`` / ``after_state``
    # so the list query doesn't fetch the JSON payload (the detail dialog gets
    # it via :meth:`get_by_id`). codex must-fix: keep the list/detail split
    # honest at the SQL layer, not just the DTO surface.
    _SUMMARY_COLUMNS = (
        AdminAuditLog.id,
        AdminAuditLog.admin_user_id,
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.domain,
        AdminAuditLog.record_id,
        AdminAuditLog.result,
        AdminAuditLog.failure_reason,
        AdminAuditLog.ip_address,
        AdminAuditLog.correlation_id,
        AdminAuditLog.created_at,
    )

    async def list_filtered(
        self,
        filter_vo: AuditLogFilter,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLogSummaryDTO], int]:
        """Return a page of summary rows + total count for the audit-log UI.

        The summary projection deliberately omits ``before_state`` /
        ``after_state`` so the list payload stays small; the detail dialog
        fetches the full row via :meth:`get_by_id`.
        """
        stmt = self._apply_filter(select(*self._SUMMARY_COLUMNS), filter_vo).order_by(
            AdminAuditLog.created_at.desc()
        )
        count_stmt = self._apply_filter(select(func.count(AdminAuditLog.id)), filter_vo)
        offset = max(page - 1, 0) * page_size

        async with self._database.session() as session:
            total = (await session.execute(count_stmt)).scalar_one()
            result = await session.execute(stmt.offset(offset).limit(page_size))
            rows = result.all()

        summaries = [
            AuditLogSummaryDTO(
                id=row.id,
                admin_user_id=row.admin_user_id,
                admin_username=row.admin_username,
                action=AdminAction(row.action),
                domain=row.domain,
                record_id=row.record_id,
                result=AuditResult(row.result),
                failure_reason=row.failure_reason,
                ip_address=row.ip_address,
                correlation_id=row.correlation_id,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return summaries, total

    async def get_by_id(self, audit_id: int) -> AuditLogDTO | None:
        """Return one full audit row (with JSON state) for the detail dialog."""
        async with self._database.session() as session:
            row = await session.get(AdminAuditLog, audit_id)
            if row is None:
                return None
            return AuditLogDTO(
                id=row.id,
                admin_user_id=row.admin_user_id,
                admin_username=row.admin_username,
                action=AdminAction(row.action),
                domain=row.domain,
                record_id=row.record_id,
                before_state=row.before_state,
                after_state=row.after_state,
                result=AuditResult(row.result),
                failure_reason=row.failure_reason,
                ip_address=row.ip_address,
                correlation_id=row.correlation_id,
                created_at=row.created_at,
            )

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete entries strictly older than ``cutoff``. Returns deleted count.

        Aware datetimes are normalized to naive UTC before binding so the
        scheduler/ad-hoc callers can pass either shape without tripping
        asyncpg's "can't compare offset-naive and offset-aware" on Postgres
        (``AdminAuditLog.created_at`` is a tz-naive column — see ``_to_naive_utc``).
        """
        naive_cutoff = self._to_naive_utc(cutoff)
        async with self._database.session() as session:
            result = await session.execute(
                delete(AdminAuditLog).where(AdminAuditLog.created_at < naive_cutoff)
            )
            await session.commit()
            return result.rowcount or 0

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _to_naive_utc(value: datetime) -> datetime:
        """Normalize a timezone-aware datetime to naive UTC.

        ``AdminAuditLog.created_at`` is ``sa.DateTime()`` — timezone-naive on
        both SQLite and Postgres. Binding aware datetimes against a naive
        column raises on asyncpg/Postgres, so callers' aware values must be
        converted before they hit the query.
        """
        if value.tzinfo is None:
            return value
        return value.astimezone(_UTC).replace(tzinfo=None)

    @classmethod
    def _apply_filter(cls, stmt, filter_vo: AuditLogFilter):
        if filter_vo.username_like:
            stmt = stmt.where(
                AdminAuditLog.admin_username.ilike(f"%{filter_vo.username_like}%")
            )
        if filter_vo.actions:
            stmt = stmt.where(
                AdminAuditLog.action.in_([a.value for a in filter_vo.actions])
            )
        if filter_vo.domains:
            stmt = stmt.where(AdminAuditLog.domain.in_(filter_vo.domains))
        if filter_vo.result is not None:
            stmt = stmt.where(AdminAuditLog.result == filter_vo.result.value)
        if filter_vo.since is not None:
            stmt = stmt.where(
                AdminAuditLog.created_at >= cls._to_naive_utc(filter_vo.since)
            )
        if filter_vo.until is not None:
            stmt = stmt.where(
                AdminAuditLog.created_at < cls._to_naive_utc(filter_vo.until)
            )
        return stmt
