"""Prompt store tables (#451, ADR 066).

Two tables, because the two facts change differently:

- ``prompt_version`` is append-only. A version's text is never updated: ledger
  rows record ``name@version``, and that reference is only meaningful if the
  text behind it cannot change.
- ``prompt_active`` holds one pointer per name. Activating, rolling back and
  reverting to the code default only move or delete that pointer.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src._core.infrastructure.persistence.rdb.database import Base


class PromptVersionModel(Base):
    __tablename__ = "prompt_version"
    __table_args__ = (
        # Also the race guard: two concurrent saves that compute the same next
        # number collide here instead of producing two v(n+1) rows.
        UniqueConstraint("name", "version", name="uq_prompt_version_name_version"),
    )

    # Same BigInteger / SQLite-INTEGER split as the audit log and ai_usage.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Username, denormalised like ``admin_audit_log.admin_username``: it must
    # survive deletion of the admin who wrote it.
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class PromptActiveModel(Base):
    __tablename__ = "prompt_active"

    name: Mapped[str] = mapped_column(String(200), primary_key=True)
    # No foreign key to prompt_version: the pair (name, version) is the
    # reference, and the write path only ever points at a version it has just
    # read. A composite FK would add a constraint the append-only table never
    # needs to defend.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    activated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
