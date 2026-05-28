"""Whitelist serializers for ``before_state`` / ``after_state`` snapshots (#196).

Critical security boundary (codex must-fix): NEVER persist the password hash,
temporary password, refresh-token hashes, raw exception messages, or any field
not explicitly allow-listed below. New fields are opt-in — add them here only
after reviewing what an operator should see in the audit-log diff.
"""

from typing import Any

from src.user.domain.dtos.user_dto import UserDTO

# Allow-list of safe fields from ``UserDTO`` for audit snapshots. ``password``
# (the bcrypt hash) is intentionally absent. New columns added to ``UserDTO``
# default to *not* being audited until explicitly added here.
_USER_AUDIT_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "username",
        "full_name",
        "email",
        "role",
        "permissions",
        "is_bootstrap_admin",
        "password_temporary",
        "created_at",
        "updated_at",
    }
)


def safe_user_snapshot(user: UserDTO | None) -> dict[str, Any] | None:
    """Return a deny-by-default JSON-safe dict of ``UserDTO`` fields.

    ``None`` in → ``None`` out (e.g. an action with no before-state). Datetime
    fields are serialized to ISO strings via Pydantic's ``mode="json"`` so the
    result drops cleanly into a ``sa.JSON`` column.
    """
    if user is None:
        return None
    return user.model_dump(mode="json", include=set(_USER_AUDIT_FIELDS))
