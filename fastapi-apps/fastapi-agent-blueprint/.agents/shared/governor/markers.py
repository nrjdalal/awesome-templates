"""Phase 2 marker writer + Phase 4 lifecycle reader (IC-11 / IC-12).

Single source of truth for:

* ``write_marker(payload, state_dir)`` — Phase 2 hook persistence
* ``read_latest_token(state_dir, lifecycle)`` — Phase 3/4 reader with
  defensive 24h filter (IC-11) and IC-12 lifecycle policy enum
* ``consume_phase2_markers(state_dir)`` — Phase 4 Stop-hook cleanup
  (read-and-delete on Stop, IC-11 Option A frozen by PR #128)
* ``MarkerLifecycle`` enum — exhaustive policy surface; new variants
  must be wired through ``read_latest_token`` and covered by an
  exhaustive match test (R0-C.2).

Behaviour invariance (HC-5.1): all three helpers mirror the pre-Phase-5
implementations. The 24h defensive filter and the read-then-delete
ordering are unchanged.
"""

from __future__ import annotations

import contextlib
import json
import time
import uuid
from enum import Enum
from pathlib import Path

from .time_window import _within_24h


class MarkerLifecycle(Enum):
    """IC-12 marker lifecycle policy.

    ``READ_ONLY`` — used by verify-first reader (Phase 3); markers stay
    on disk until Stop consumes them.

    ``READ_AND_DELETE`` — used by completion-gate Stop hook (Phase 4
    Option A frozen by IC-11). Stop hook deletes Phase 2 markers after
    reading so the next session does not inherit stale exception state.

    Adding a new variant is a contract change: update
    ``read_latest_token`` and the exhaustive lifecycle test.
    """

    READ_ONLY = "read_only"
    READ_AND_DELETE = "read_and_delete"


def write_marker(payload: dict, state_dir: Path) -> Path | None:
    """Write the token decision payload to a per-session marker file.

    Marker schema: ``{matched, token, rationale_required, ts}`` where
    ``ts`` is an ISO 8601 UTC timestamp. Returns the marker path on
    write, or ``None`` when ``payload['matched']`` is falsy.
    """

    if not payload.get("matched"):
        return None
    state_dir.mkdir(parents=True, exist_ok=True)
    ts_compact = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    marker = state_dir / f"exception-token-{ts_compact}-{uuid.uuid4().hex[:12]}.json"
    record = dict(payload)
    record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    marker.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return marker


def read_latest_token(
    state_dir: Path, lifecycle: MarkerLifecycle = MarkerLifecycle.READ_ONLY
) -> str | None:
    """Return the most recent valid Phase 2 token, or ``None``.

    Filters out markers older than 24 hours (IC-11 defensive filter
    against orphans from prior sessions). When ``lifecycle`` is
    ``READ_AND_DELETE`` the matching markers are removed after reading.
    """

    if not state_dir.exists():
        return None

    # Parity contract (R1-A.1): pre-Phase-5 readers checked only that
    # ``ts`` and ``token`` are strings within the 24h window. They did NOT
    # require ``matched=True`` because ``write_marker`` already gates on
    # that field. Stay byte-compatible — do not enforce ``matched`` here.
    candidates: list[tuple[str, str, Path]] = []
    for marker in state_dir.glob("exception-token-*.json"):
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        ts = data.get("ts")
        if not isinstance(ts, str) or not _within_24h(ts):
            continue
        token = data.get("token")
        if not isinstance(token, str):
            continue
        candidates.append((ts, token, marker))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    _, latest_token, _ = candidates[-1]

    if lifecycle is MarkerLifecycle.READ_AND_DELETE:
        for _, _, marker in candidates:
            with contextlib.suppress(OSError):
                marker.unlink()

    return latest_token


def consume_phase2_markers(state_dir: Path) -> None:
    """Delete every ``exception-token-*.json`` marker under ``state_dir``.

    Phase 4 IC-11 Option A — Stop hook calls this once per session
    regardless of whether a token was matched, so partially-parsed or
    malformed markers do not survive into the next session.
    """

    if not state_dir.exists():
        return
    for marker in state_dir.glob("exception-token-*.json"):
        with contextlib.suppress(OSError):
            marker.unlink()
