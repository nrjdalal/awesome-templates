"""Shared work ledger — cross-session context persistence.

Keeps the current work context alive across sessions so Claude and Codex
can resume without losing scope, plan, or verification state.

State file: .agents/state/current-work.json  (gitignored)

Schema v1
---------
{
  "schema_version": 1,
  "meta": {
    "updated_at": "<ISO8601>",
    "updated_by": "claude|codex|skill|manual",
    "session_id": "<optional string>"
  },
  "last_prompt": "<full text of last UserPromptSubmit>",
  "goal": "<user-stated or skill-set goal — null when unset>",
  "scope": "<affected domains/files — null when unset>",
  "plan": "<structured plan text — null when unset>",
  "blockers": "<known blockers — null when unset>",
  "verification": {
    "status": "unknown|pending|passed|failed",
    "last_verified_at": "<ISO8601 or null>",
    "last_command": "<last verify command string or null>",
    "changed_py_files": ["<repo-relative .py paths changed since last verify>"]
  }
}

Hook integration
----------------
- SessionStart  : read_ledger() → inject_summary()
- UserPromptSubmit : update_last_prompt()
- Stop          : update_verification_from_git() + write_ledger()
- Skills        : update_goal_scope_plan()

Design constraints
------------------
- All public functions are fail-open: I/O errors return None / empty safely.
- No top-level side effects — callers drive all reads and writes.
- IC-14: no governor policy inline — this module owns only ledger I/O.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = Path(os.environ.get("HARNESS_STATE_ROOT", REPO_ROOT))
STATE_DIR = STATE_ROOT / ".agents" / "state"
LEDGER_PATH = STATE_DIR / "current-work.json"

SCHEMA_VERSION = 1

# Maximum characters of last_prompt stored (avoids bloating the ledger).
_PROMPT_MAX_CHARS = 1200


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _default_ledger() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "updated_at": _now_iso(),
            "updated_by": "system",
            "session_id": None,
        },
        "last_prompt": None,
        "goal": None,
        "scope": None,
        "plan": None,
        "blockers": None,
        "verification": {
            "status": "unknown",
            "last_verified_at": None,
            "last_command": None,
            "changed_py_files": [],
        },
    }


def read_ledger() -> dict | None:
    """Return the current ledger, or None if absent / unreadable."""
    with contextlib.suppress(Exception):
        text = LEDGER_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
            return data
    return None


def write_ledger(data: dict, updated_by: str = "system") -> bool:
    """Persist the ledger. Returns True on success."""
    with contextlib.suppress(Exception):
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("meta", {})
        data["meta"]["updated_at"] = _now_iso()
        data["meta"]["updated_by"] = updated_by
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    return False


def _changed_py_files() -> list[str]:
    """Collect uncommitted/untracked .py files (fail-open)."""
    with contextlib.suppress(Exception):
        tracked = subprocess.run(  # noqa: S603,S607
            ["git", "diff", "--name-only", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        untracked = subprocess.run(  # noqa: S603,S607
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return sorted(
            {
                p
                for chunk in (tracked, untracked)
                for p in chunk.splitlines()
                if p.endswith(".py")
            }
        )
    return []


# ---------------------------------------------------------------------------
# Public update helpers
# ---------------------------------------------------------------------------


def update_last_prompt(prompt: str, session_id: str | None = None) -> None:
    """Store the latest prompt text (truncated). Called from UserPromptSubmit."""
    ledger = read_ledger() or _default_ledger()
    ledger["last_prompt"] = prompt[:_PROMPT_MAX_CHARS] if prompt else None
    if session_id:
        ledger.setdefault("meta", {})["session_id"] = session_id
    write_ledger(ledger, updated_by="hook:user_prompt_submit")


def update_verification_from_git() -> None:
    """Refresh changed_py_files from git. Called from Stop hook."""
    ledger = read_ledger() or _default_ledger()
    py_files = _changed_py_files()
    verification = ledger.setdefault("verification", {})
    verification["changed_py_files"] = py_files
    # Promote status to "pending" only when files exist and status was unknown.
    if py_files and verification.get("status") == "unknown":
        verification["status"] = "pending"
    write_ledger(ledger, updated_by="hook:stop")


def update_goal_scope_plan(
    goal: str | None = None,
    scope: str | None = None,
    plan: str | None = None,
    updated_by: str = "skill",
) -> None:
    """Set goal / scope / plan fields. Called from plan-feature, new-domain, etc."""
    ledger = read_ledger() or _default_ledger()
    if goal is not None:
        ledger["goal"] = goal
    if scope is not None:
        ledger["scope"] = scope
    if plan is not None:
        ledger["plan"] = plan
    write_ledger(ledger, updated_by=updated_by)


def mark_verified(command: str, passed: bool) -> None:
    """Record a verify-command result. Called from verify-aware hooks/skills."""
    ledger = read_ledger() or _default_ledger()
    verification = ledger.setdefault("verification", {})
    verification["status"] = "passed" if passed else "failed"
    verification["last_verified_at"] = _now_iso()
    verification["last_command"] = command
    # Clear pending py_files on pass.
    if passed:
        verification["changed_py_files"] = []
    write_ledger(ledger, updated_by="hook:verify")


# ---------------------------------------------------------------------------
# SessionStart injection
# ---------------------------------------------------------------------------


def build_session_summary() -> str | None:
    """Return a one-paragraph context summary for SessionStart injection.

    Returns None when no ledger exists or ledger contains no meaningful state
    (all of goal/last_prompt/verification are unset/unknown).
    """
    ledger = read_ledger()
    if not ledger:
        return None

    parts: list[str] = []

    goal = ledger.get("goal")
    scope = ledger.get("scope")
    plan = ledger.get("plan")
    last_prompt = ledger.get("last_prompt")
    blockers = ledger.get("blockers")
    verification = ledger.get("verification") or {}
    v_status = verification.get("status", "unknown")
    v_cmd = verification.get("last_command")
    py_files = verification.get("changed_py_files") or []
    updated_at = (ledger.get("meta") or {}).get("updated_at", "?")

    # Only inject when there is something useful to say.
    has_content = any([goal, last_prompt, v_status != "unknown", py_files])
    if not has_content:
        return None

    parts.append(f"[work-ledger] Resuming session — last updated {updated_at}")
    if goal:
        parts.append(f"  Goal     : {goal}")
    if scope:
        parts.append(f"  Scope    : {scope}")
    if plan:
        # Truncate long plans to avoid bloating the system message.
        plan_preview = plan[:300] + "…" if len(plan) > 300 else plan
        parts.append(f"  Plan     : {plan_preview}")
    if blockers:
        parts.append(f"  Blockers : {blockers}")

    # Verification status
    v_label = {
        "unknown": "unknown (no verify run recorded)",
        "pending": f"pending — {len(py_files)} .py file(s) changed since last verify",
        "passed": f"passed (last: {v_cmd})" if v_cmd else "passed",
        "failed": f"FAILED (last: {v_cmd})" if v_cmd else "FAILED",
    }.get(v_status, v_status)
    parts.append(f"  Verify   : {v_label}")
    if py_files and v_status in ("unknown", "pending", "failed"):
        parts.append(
            "  Modified : "
            + ", ".join(py_files[:6])
            + (" …" if len(py_files) > 6 else "")
        )

    if last_prompt:
        preview = last_prompt[:200] + "…" if len(last_prompt) > 200 else last_prompt
        parts.append(f"  Last msg : {preview}")

    return "\n".join(parts)
