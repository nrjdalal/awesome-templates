#!/usr/bin/env python3
"""CLI bridge for governor.paths.resolve_session_roots — bash integration (#425).

Reads a hook payload (JSON) from stdin and always prints exactly one line:

* the top level of the session's working tree — re-rooted;
* ``none`` — the payload has no ``cwd``: the caller keeps its own checkout
  (the pre-#425 behaviour);
* ``rejected`` — the payload names a ``cwd`` this harness cannot place, or the
  payload or resolver failed: the caller skips session-scoped work rather than
  fall back to its own checkout (see ``governor.paths.SessionRoots``).

No output at all therefore means the resolver never ran (no interpreter, a
broken import). The shell caller then cannot trust either answer and falls back
to its own containment check (``_cwd_inside_this_checkout`` in
``stop-sync-reminder.sh``). Always exits 0 — HC-5.5 fail-open.

Invocation (from .claude/hooks/stop-sync-reminder.sh):
  printf '%s' "$INPUT" \\
    | PYTHONPATH="$SHARED_DIR" sh "$PY_LAUNCHER" -m governor.session_root_cli
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    try:
        from governor.paths import resolve_session_roots

        roots = resolve_session_roots(json.loads(sys.stdin.read() or "{}"))
    except Exception:  # noqa: BLE001 — HC-5.5: a payload we cannot read is not ours
        print("rejected")
        return
    if roots.rejected:
        print("rejected")
    elif roots.repo_root is not None:
        print(roots.repo_root)
    else:
        print("none")


if __name__ == "__main__":
    main()
