"""24-hour ISO 8601 timestamp window helper.

Single source of truth for the ``_within_24h`` helper that Phase 2/3/4
hook scripts duplicated across four sites
(``.{claude,codex}/hooks/{verify_first,completion_gate}.py``).

Behaviour invariance contract (HC-5.1): identical input must produce
identical output to the pre-Phase-5 implementations. The body therefore
mirrors the original verbatim — including the defensive ``except`` that
returns ``True`` on parse failure (treating malformed timestamps as
"recent" so callers do not silently expire on garbage input).
"""

from __future__ import annotations

from datetime import UTC, datetime


def _within_24h(ts: str) -> bool:
    """Return True if ``ts`` is an ISO 8601 UTC timestamp within 24h."""

    try:
        dt = datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=UTC)
        return (datetime.now(tz=UTC) - dt).total_seconds() < 86400
    except Exception:  # noqa: BLE001 — preserve pre-refactor fail-soft contract
        return True
