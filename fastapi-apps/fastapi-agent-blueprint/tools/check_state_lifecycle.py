#!/usr/bin/env python3
"""State lifecycle health check — pre-commit integration (PR-A.3).

Two-tier policy:
  FAIL-HARD (exit 1) — git-tracked files exist under .claude/state/,
    .codex/state/, or .antigravity/state/: the .gitignore guard has been
    bypassed and exception-token or verify-log files may be committed to
    version control.

  WARN-ONLY (exit 0 + stderr) — stale marker count exceeds the threshold K.
    A non-zero stale count is informational: the Stop hook may not have fired
    recently, but it is not a commit-blocking error.

Usage (pre-commit entry):
  python3 tools/check_state_lifecycle.py
  (pass_filenames: false — the tool checks fixed directories, not changed files)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_DIRS = (
    REPO_ROOT / ".claude" / "state",
    REPO_ROOT / ".codex" / "state",
    REPO_ROOT / ".antigravity" / "state",
)
# Warn when the total stale-marker count across state dirs reaches this.
_STALE_WARN_THRESHOLD = 10


def _git_tracked_state_files() -> list[str]:
    """Return a list of git-tracked paths inside the state directories."""
    tracked: list[str] = []
    for pattern in (".claude/state/", ".codex/state/", ".antigravity/state/"):
        result = subprocess.run(  # noqa: S603
            ["git", "ls-files", pattern],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        tracked.extend(line for line in result.stdout.splitlines() if line)
    return tracked


def _stale_counts(state_dir: Path) -> dict[str, int]:
    """Return {'total': N, 'stale': M} marker counts for *state_dir*."""
    if not state_dir.exists():
        return {"total": 0, "stale": 0}

    now = time.time()
    total = 0
    stale = 0
    for pattern in ("exception-token-*.json", "verify-log-*.json"):
        for path in state_dir.glob(pattern):
            total += 1
            try:
                if (now - path.stat().st_mtime) > 86400:  # 24 h
                    stale += 1
            except OSError:
                pass
    return {"total": total, "stale": stale}


def main() -> int:
    # ------------------------------------------------------------------ #
    # FAIL-HARD: tracked state files in version control                   #
    # ------------------------------------------------------------------ #
    tracked = _git_tracked_state_files()
    if tracked:
        print(
            "check_state_lifecycle: FAIL — git-tracked state files detected:",
            file=sys.stderr,
        )
        for f in tracked:
            print(f"  {f}", file=sys.stderr)
        print(
            "\nThese files must not be committed.  Add them to .gitignore or run:\n"
            "  git rm --cached .claude/state/ .codex/state/ .antigravity/state/",
            file=sys.stderr,
        )
        return 1

    # ------------------------------------------------------------------ #
    # WARN-ONLY: stale marker accumulation                                #
    # ------------------------------------------------------------------ #
    total_stale = 0
    for state_dir in _STATE_DIRS:
        counts = _stale_counts(state_dir)
        if counts["stale"] > 0:
            rel = state_dir.relative_to(REPO_ROOT)
            print(
                f"check_state_lifecycle: WARNING — {counts['stale']} stale marker(s)"
                f" in {rel}/ (total: {counts['total']})."
                " Stop hook may not have fired recently.",
                file=sys.stderr,
            )
        total_stale += counts["stale"]

    if total_stale > _STALE_WARN_THRESHOLD:
        print(
            f"check_state_lifecycle: WARNING — {total_stale} stale markers"
            f" exceed threshold ({_STALE_WARN_THRESHOLD})."
            " Run: python3 tools/governor_state_doctor.py",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
