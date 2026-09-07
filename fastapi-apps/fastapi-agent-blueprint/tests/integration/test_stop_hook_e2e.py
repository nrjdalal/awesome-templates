"""E2E integration test: Codex stop-sync-reminder.py marker cleanup (PR-A.3).

Runs .codex/hooks/stop-sync-reminder.py as a real subprocess against the live
.codex/state/ directory.  Verifies that both fresh and stale exception-token
markers written by this test are consumed by the hook's Phase 4 cleanup.

Stripped environment: only PATH + HOME are forwarded to the subprocess,
simulating a minimal agent invocation without project-specific env vars.

IMPORTANT: this test writes to the real .codex/state/ directory so it
exercises the actual production lifecycle path.  A finally block removes any
markers the hook failed to consume so CI stays clean.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK = REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"
_STATE_DIR = REPO_ROOT / ".codex" / "state"

# Unique infix so the finally block can identify markers created by this test
# even if a real session runs concurrently.
_E2E_INFIX = "e2etest"

_LEDGER_PATH = REPO_ROOT / ".agents" / "state" / "current-work.json"


def _read_live_ledger() -> str | None:
    """Exact bytes of the live work ledger, or ``None`` when it is absent."""
    try:
        return _LEDGER_PATH.read_text(encoding="utf-8")
    except OSError:
        return None


def _restore_live_ledger(snapshot: str | None) -> None:
    """Put the live work ledger back the way this test found it (#407)."""
    if snapshot is None:
        _LEDGER_PATH.unlink(missing_ok=True)
        return
    if _read_live_ledger() != snapshot:
        _LEDGER_PATH.write_text(snapshot, encoding="utf-8")


def test_stop_hook_e2e_marker_cleanup() -> None:
    """stop-sync-reminder.py must consume all exception-token markers on Stop."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)

    now = time.time()
    stale_epoch = now - (48 * 3600)
    written: list[Path] = []
    # The stripped env below is built from scratch, so this test inherits none
    # of the session isolation that `tests/conftest.py` installs (#407) — and
    # that is deliberate, because the markers under test live in the *real*
    # `.codex/state/`. What is not deliberate is the rest of the Stop hook's
    # work: it also calls `update_verification_from_git()`, which rewrites the
    # operator's live `.agents/state/current-work.json`. Snapshot it and put it
    # back, the same contract the marker cleanup below already honours.
    ledger_before = _read_live_ledger()

    try:
        # 3 fresh markers (within 24 h — removed by IC-11 Option A bulk sweep)
        for i in range(3):
            ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            ts_compact = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
            marker = (
                _STATE_DIR / f"exception-token-{ts_compact}-{_E2E_INFIX}f{i:012d}.json"
            )
            marker.write_text(
                json.dumps({"matched": True, "token": "trivial", "ts": ts_iso}),
                encoding="utf-8",
            )
            written.append(marker)

        # 5 stale markers (48 h ago — also removed by bulk sweep regardless of age)
        for i in range(5):
            ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stale_epoch))
            ts_compact = time.strftime("%Y%m%dT%H%M%S", time.gmtime(stale_epoch))
            marker = (
                _STATE_DIR / f"exception-token-{ts_compact}-{_E2E_INFIX}s{i:012d}.json"
            )
            marker.write_text(
                json.dumps({"matched": True, "token": "trivial", "ts": ts_iso}),
                encoding="utf-8",
            )
            os.utime(marker, (stale_epoch, stale_epoch))
            written.append(marker)

        # Stripped env: only PATH + HOME (no CODEX_THREAD_ID, AGENT_LOCALE, etc.)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
            "HOME": os.environ.get("HOME", str(Path.home())),
        }

        proc = subprocess.run(
            [sys.executable, str(_HOOK)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        assert proc.returncode == 0, (
            f"stop-sync-reminder.py exited with code {proc.returncode}\n"
            f"stdout: {proc.stdout[:800]}\n"
            f"stderr: {proc.stderr[:800]}"
        )

        # All 8 markers must be gone — consume_phase2_markers sweeps the glob
        remaining = [m for m in written if m.exists()]
        assert not remaining, (
            f"{len(remaining)}/8 e2e marker(s) survived the Stop hook sweep:\n"
            + "\n".join(f"  {m.name}" for m in remaining)
        )

        # stdout must be valid JSON (IC-2: single Stop event JSON line or empty)
        stdout = proc.stdout.strip()
        if stdout:
            try:
                json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"Hook stdout is not valid JSON: {exc}\nstdout: {stdout[:400]}"
                ) from exc

    finally:
        # Defensive cleanup: remove any markers this test created that survived
        for marker in written:
            if marker.exists():
                marker.unlink(missing_ok=True)
        _restore_live_ledger(ledger_before)
