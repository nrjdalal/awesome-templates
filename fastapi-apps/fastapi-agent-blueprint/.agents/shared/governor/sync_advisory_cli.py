#!/usr/bin/env python3
"""CLI bridge for governor.sync_advisory — bash integration (F-1).

Reads newline-separated file paths from stdin.  Writes to stdout:
  Line 1: "foundation" | "structure" | "none"
  Lines 2+: matched file paths (omitted when level is "none")

Always exits 0 — HC-5.5 fail-open: any exception produces "none" so the
calling bash hook can use the result without error-path branching.

Invocation (from .claude/hooks/stop-sync-reminder.sh):
  printf '%s\\n' "$CHANGED" \\
    | PYTHONPATH="$SHARED_DIR" python3 -m governor.sync_advisory_cli
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from governor.sync_advisory import classify_advisory

        lines = sys.stdin.read().splitlines()
        changed = [line for line in lines if line]
        level, files = classify_advisory(changed)
        level_str = level if level is not None else "none"
        print(level_str)
        for f in files:
            print(f)
    except Exception:  # noqa: BLE001
        # HC-5.5 fail-open: import error or runtime error → no advisory
        print("none")


if __name__ == "__main__":
    main()
