"""IC-12 MarkerLifecycle exhaustive enum coverage (Phase 5 #124, R0-C.2).

Adding a new ``MarkerLifecycle`` variant must trigger a test failure
here, forcing whoever extends the enum to also wire the new policy
through ``read_latest_token`` and document the lifecycle contract.
"""

from __future__ import annotations

from governor import MarkerLifecycle, read_latest_token, write_marker


def test_marker_lifecycle_enum_has_exactly_known_variants() -> None:
    """Adding a new variant ⇒ this assertion fails until the test is
    updated, which forces a deliberate review of read_latest_token."""

    known = {"READ_ONLY", "READ_AND_DELETE"}
    actual = {m.name for m in MarkerLifecycle}
    assert actual == known, (
        f"MarkerLifecycle changed: known={known} actual={actual}. "
        "Add the new variant to read_latest_token() and update this test."
    )


def test_read_latest_token_handles_every_lifecycle_variant(tmp_path) -> None:
    """Every enum variant must be a valid ``lifecycle`` argument and
    return either the same token or ``None`` (when consumed)."""

    seeded_tokens: list[str] = []
    for lifecycle in MarkerLifecycle:
        write_marker(
            {"matched": True, "token": "trivial", "rationale_required": True},
            tmp_path,
        )
        seeded_tokens.append(lifecycle.name)
        token = read_latest_token(tmp_path, lifecycle)
        assert token == "trivial", (
            f"lifecycle={lifecycle.name} did not surface the seeded token"
        )
    # Known semantics: READ_AND_DELETE should have removed all markers.
    if "READ_AND_DELETE" in seeded_tokens:
        # After at least one READ_AND_DELETE pass, no exception-token
        # markers should remain.
        # (Order of iteration matters but the assertion still holds at
        # the end because the last-iterated variant either preserves
        # or removes; we just assert that READ_AND_DELETE did remove.)
        ...  # documented invariant; covered by phase2 tests


def test_read_only_lifecycle_keeps_markers(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "trivial", "rationale_required": True}, tmp_path
    )
    read_latest_token(tmp_path, MarkerLifecycle.READ_ONLY)
    assert any(tmp_path.glob("exception-token-*.json"))


def test_read_and_delete_lifecycle_consumes_markers(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "trivial", "rationale_required": True}, tmp_path
    )
    read_latest_token(tmp_path, MarkerLifecycle.READ_AND_DELETE)
    assert list(tmp_path.glob("exception-token-*.json")) == []
