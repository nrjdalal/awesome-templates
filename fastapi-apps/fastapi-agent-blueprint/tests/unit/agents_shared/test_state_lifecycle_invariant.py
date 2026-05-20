"""Lifecycle invariant unit guards (PR-A.3).

Five regression guards that protect the Phase 2/4 state lifecycle:

  1. Corrupt JSON markers are skipped by read_latest_token (no crash).
  2. Garbage ts values are skipped by read_latest_token (no crash).
  3. Bulk consume of 200 stale markers completes in < 5 seconds.
  4. stop-sync-reminder.py static check: both consume_phase2_markers and
     cleanup_stale_verify_logs are still called (neither may be dropped).
  5. Cross-reference: the AST-based fixture leak guard (test_no_test_state_leak.py)
     must be present and contain its key test function.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agents" / "shared"))

from governor.markers import consume_phase2_markers, read_latest_token

# ---------------------------------------------------------------------------
# Guard 1 — corrupt JSON skipped by read_latest_token
# ---------------------------------------------------------------------------


def test_corrupt_json_skipped(tmp_path: Path) -> None:
    """Corrupt JSON markers must be silently skipped, not raise."""
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "exception-token-20260101T000000-corrupt000001.json").write_text(
        "{not valid json",
        encoding="utf-8",
    )
    result = read_latest_token(state_dir)
    assert result is None


# ---------------------------------------------------------------------------
# Guard 2 — garbage ts treated as within-24h (fail-soft contract)
# ---------------------------------------------------------------------------


def test_garbage_ts_treated_as_recent(tmp_path: Path) -> None:
    """_within_24h returns True on parse failure (HC-5.1 fail-soft contract).

    A marker with an unparseable ts must NOT be silently dropped — it is treated
    as "recent" so callers never silently expire on garbage input.  This test
    guards the invariant: garbage ts → token still returned, no exception raised.
    """
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True)
    marker = state_dir / "exception-token-20260101T000000-garbts000001.json"
    marker.write_text(
        json.dumps({"matched": True, "token": "trivial", "ts": "not-a-timestamp"}),
        encoding="utf-8",
    )
    # Garbage ts → _within_24h returns True → marker is kept, token is returned
    result = read_latest_token(state_dir)
    assert result == "trivial", (
        "Garbage ts must be treated as recent (fail-soft), not silently dropped"
    )


def test_missing_ts_field_skipped(tmp_path: Path) -> None:
    """Markers missing the ts field entirely are silently skipped."""
    state_dir = tmp_path / ".codex" / "state"
    state_dir.mkdir(parents=True)
    marker = state_dir / "exception-token-20260101T000000-nots0000001.json"
    marker.write_text(
        json.dumps({"matched": True, "token": "trivial"}),
        encoding="utf-8",
    )
    result = read_latest_token(state_dir)
    assert result is None


# ---------------------------------------------------------------------------
# Guard 3 — 200-marker bulk consume completes quickly
# ---------------------------------------------------------------------------


def test_bulk_200_markers_consume(tmp_path: Path) -> None:
    """consume_phase2_markers must handle 200 stale markers in < 5 seconds."""
    state_dir = tmp_path / ".codex" / "state"
    state_dir.mkdir(parents=True)

    stale_epoch = time.time() - (7 * 24 * 3600)  # 7 days ago
    stale_ts_compact = time.strftime("%Y%m%dT%H%M%S", time.gmtime(stale_epoch))
    stale_ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stale_epoch))

    for i in range(200):
        marker = state_dir / f"exception-token-{stale_ts_compact}-bulk{i:012d}.json"
        marker.write_text(
            json.dumps({"matched": True, "token": "trivial", "ts": stale_ts_iso}),
            encoding="utf-8",
        )
        os.utime(marker, (stale_epoch, stale_epoch))

    assert len(list(state_dir.glob("exception-token-*.json"))) == 200

    t0 = time.monotonic()
    consume_phase2_markers(state_dir)
    elapsed = time.monotonic() - t0

    remaining = list(state_dir.glob("exception-token-*.json"))
    assert not remaining, f"{len(remaining)} markers survived bulk consume"
    assert elapsed < 5.0, f"Bulk consume took {elapsed:.2f}s (limit: 5s)"


# ---------------------------------------------------------------------------
# Guard 4 — stop-sync-reminder.py calls both cleanup functions (static)
# ---------------------------------------------------------------------------


def test_stop_hook_calls_consume_phase2_markers() -> None:
    """stop-sync-reminder.py must call consume_phase2_markers. Regression guard."""
    hook_text = (REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py").read_text(
        encoding="utf-8"
    )
    assert "consume_phase2_markers" in hook_text, (
        "REGRESSION: stop-sync-reminder.py no longer calls consume_phase2_markers. "
        "Phase 2 marker cleanup (IC-11 Option A) must be preserved."
    )


def test_stop_hook_calls_cleanup_stale_verify_logs() -> None:
    """stop-sync-reminder.py must call cleanup_stale_verify_logs. Regression guard."""
    hook_text = (REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py").read_text(
        encoding="utf-8"
    )
    assert "cleanup_stale_verify_logs" in hook_text, (
        "REGRESSION: stop-sync-reminder.py no longer calls cleanup_stale_verify_logs. "
        "Stale verify-log cleanup must be preserved."
    )


# ---------------------------------------------------------------------------
# Guard 5 — fixture leak guard cross-reference
# ---------------------------------------------------------------------------


def test_fixture_leak_guard_exists() -> None:
    """The AST-based fixture leak guard file must exist and be intact."""
    guard_file = (
        REPO_ROOT / "tests" / "unit" / "agents_shared" / "test_no_test_state_leak.py"
    )
    assert guard_file.exists(), (
        f"test_no_test_state_leak.py not found at {guard_file}. "
        "This file guards against fixtures writing to real state dirs."
    )
    text = guard_file.read_text(encoding="utf-8")
    assert "test_no_fixture_writes_real_state_dir" in text, (
        "Key guard 'test_no_fixture_writes_real_state_dir' is missing from "
        "test_no_test_state_leak.py — the guard may have been accidentally removed."
    )
