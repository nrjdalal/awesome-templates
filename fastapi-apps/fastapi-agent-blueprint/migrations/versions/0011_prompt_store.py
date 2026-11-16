"""prompt store: append-only versions + active pointer (#451, ADR 066)

Revision ID: 0011_prompt_store
Revises: 0010_drop_audit_actor_fk
Create Date: 2026-11-16

Two new tables, nothing else touched. ``prompt_version`` is append-only (the
application never updates a row); ``prompt_active`` holds one pointer per prompt
name. With no rows, every agent serves the code text exactly as before.

Zero-downtime note (ADR 056): purely additive. ``CREATE TABLE`` with its unique
constraint on an empty table takes no lock on existing data, and the old
application version never reads these tables, so old and new versions both run
across the deploy. Downgrade drops both tables, which discards stored prompt
versions — agents fall back to the code text.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_prompt_store"
down_revision: str | None = "0010_drop_audit_actor_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_version",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", "version", name="uq_prompt_version_name_version"),
    )
    op.create_table(
        "prompt_active",
        sa.Column("name", sa.String(200), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("activated_by", sa.String(100), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("prompt_active")
    op.drop_table("prompt_version")
