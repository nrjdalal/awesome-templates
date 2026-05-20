"""Unit tests for shared governor time window helper.

Phase 5 (#124) commit 1 — sanity check that ``_within_24h`` is importable
via the shared package and preserves the fail-soft semantics that the
four duplicated copies relied on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from governor.time_window import _within_24h


def test_within_24h_fresh_timestamp_returns_true() -> None:
    now = datetime.now(tz=UTC).isoformat()
    assert _within_24h(now) is True


def test_within_24h_stale_timestamp_returns_false() -> None:
    stale = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    assert _within_24h(stale) is False


def test_within_24h_just_under_boundary_returns_true() -> None:
    just_under = (datetime.now(tz=UTC) - timedelta(hours=23, minutes=59)).isoformat()
    assert _within_24h(just_under) is True


def test_within_24h_just_over_boundary_returns_false() -> None:
    just_over = (datetime.now(tz=UTC) - timedelta(hours=24, minutes=1)).isoformat()
    assert _within_24h(just_over) is False


def test_within_24h_iso_with_z_suffix_returns_true() -> None:
    now = datetime.now(tz=UTC).replace(microsecond=0)
    iso_z = now.isoformat().replace("+00:00", "") + "Z"
    assert _within_24h(iso_z) is True


def test_within_24h_malformed_returns_true_fail_soft() -> None:
    """Pre-Phase-5 contract: parse failure treated as 'recent' (fail-soft)."""

    assert _within_24h("not-a-timestamp") is True
    assert _within_24h("") is True
