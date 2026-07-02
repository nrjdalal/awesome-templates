"""Shared work ledger — cross-session context persistence.

Keeps the current work context alive across sessions so Claude and Codex
can resume without losing scope, plan, or verification state.

State file: .agents/state/current-work.json  (gitignored)

Schema v2
---------
{
  "schema_version": 2,
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
  },
  "workflow": {
    "stage": "idle|planned|executing|reviewing|complete|blocked",
    "plan_ref": "<plan or PR/issue reference, or null>",
    "current_task": "<current task title, or null>",
    "tasks": [{"id": "<stable id>", "title": "<task>", "status": "<status>"}],
    "review": {
      "mode": "codex-cli|claude-code|self-structured|human:<handle>|null",
      "status": "not_required|pending|fallback|complete|blocked",
      "reason": "<fallback/blocking rationale, or null>"
    }
  }
}

Hook integration
----------------
- SessionStart  : read_ledger() → inject_summary()
- UserPromptSubmit : update_last_prompt()
- Stop          : update_verification_from_git() + build_workflow_advisory_segments()
- Skills        : update_goal_scope_plan() + update_workflow_state()

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

SCHEMA_VERSION = 2

# Maximum characters of last_prompt stored (avoids bloating the ledger).
_PROMPT_MAX_CHARS = 1200
_UNSET = object()


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
        "workflow": _default_workflow(),
    }


def _default_workflow() -> dict:
    return {
        "stage": "idle",
        "plan_ref": None,
        "current_task": None,
        "tasks": [],
        "review": {
            "mode": None,
            "status": "not_required",
            "reason": None,
        },
    }


def _normalise_workflow(value: object) -> dict:
    workflow = _default_workflow()
    if not isinstance(value, dict):
        return workflow

    for key in ("stage", "plan_ref", "current_task"):
        if key in value:
            workflow[key] = value.get(key)

    tasks = value.get("tasks")
    if isinstance(tasks, list):
        workflow["tasks"] = [item for item in tasks if isinstance(item, dict)]

    review = value.get("review")
    if isinstance(review, dict):
        workflow["review"].update(
            {
                "mode": review.get("mode"),
                "status": review.get("status", workflow["review"]["status"]),
                "reason": review.get("reason"),
            }
        )
    return workflow


def _migrate_ledger(data: dict) -> dict | None:
    version = data.get("schema_version")
    if version not in (1, 2):
        return None

    ledger = _default_ledger()
    for key in ("meta", "last_prompt", "goal", "scope", "plan", "blockers"):
        if key in data:
            ledger[key] = data[key]

    verification = data.get("verification")
    if isinstance(verification, dict):
        ledger["verification"].update(verification)

    ledger["workflow"] = _normalise_workflow(data.get("workflow"))
    ledger["schema_version"] = SCHEMA_VERSION
    return ledger


def read_ledger() -> dict | None:
    """Return the current ledger, or None if absent / unreadable."""
    with contextlib.suppress(Exception):
        text = LEDGER_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return _migrate_ledger(data)
    return None


def write_ledger(data: dict, updated_by: str = "system") -> bool:
    """Persist the ledger. Returns True on success."""
    with contextlib.suppress(Exception):
        data = _migrate_ledger(data) or data
        data["schema_version"] = SCHEMA_VERSION
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


def update_workflow_state(
    *,
    stage: object = _UNSET,
    plan_ref: object = _UNSET,
    current_task: object = _UNSET,
    tasks: object = _UNSET,
    review_mode: object = _UNSET,
    review_status: object = _UNSET,
    review_reason: object = _UNSET,
    updated_by: str = "skill:execute-plan",
) -> None:
    """Update native workflow state for plan-feature / execute-plan."""

    ledger = read_ledger() or _default_ledger()
    workflow = _normalise_workflow(ledger.get("workflow"))
    if stage is not _UNSET:
        workflow["stage"] = stage
    if plan_ref is not _UNSET:
        workflow["plan_ref"] = plan_ref
    if current_task is not _UNSET:
        workflow["current_task"] = current_task
    if tasks is not _UNSET:
        workflow["tasks"] = (
            [item for item in tasks if isinstance(item, dict)]
            if isinstance(tasks, list)
            else []
        )
    if review_mode is not _UNSET:
        workflow["review"]["mode"] = review_mode
    if review_status is not _UNSET:
        workflow["review"]["status"] = review_status
    if review_reason is not _UNSET:
        workflow["review"]["reason"] = review_reason
    ledger["workflow"] = workflow
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


def build_workflow_advisory_segments(
    *,
    changed_files: list[str],
    governor_changing: bool,
) -> list[str]:
    """Return advisory-only native workflow reminders for Stop hooks.

    The helper is intentionally non-blocking. It records missing workflow
    state as guidance, while CI and future hardening PRs decide which
    high-confidence conditions become hard gates.
    """

    with contextlib.suppress(Exception):
        if not changed_files:
            return []
        ledger = read_ledger() or _default_ledger()
        workflow = _normalise_workflow(ledger.get("workflow"))
        verification = ledger.get("verification") or {}
        segments: list[str] = []

        if governor_changing and not workflow.get("plan_ref"):
            segments.append(
                "\n".join(
                    [
                        "[native-workflow] Native workflow advisory.",
                        "Governor-changing work should have an Execution Packet before implementation.",
                        "Run `/plan-feature` or `$plan-feature`, then continue through execute-plan.",
                    ]
                )
            )

        review = workflow.get("review") or {}
        review_status = review.get("status")
        if governor_changing and review_status in (None, "not_required", "pending"):
            segments.append(
                "\n".join(
                    [
                        "[native-workflow] Native workflow advisory.",
                        "Governor-changing work is missing review state.",
                        "Default: cross-tool review by the other harness; fallback: self-structured or human review with PR Footer rationale.",
                    ]
                )
            )

        py_files = verification.get("changed_py_files") or []
        if verification.get("status") in ("pending", "failed") and py_files:
            segments.append(
                "\n".join(
                    [
                        "[native-workflow] Native workflow advisory.",
                        f"Workflow verification is pending for {len(py_files)} Python file(s).",
                        "Changed Python files: " + ", ".join(py_files[:6]),
                    ]
                )
            )
        return segments
    return []


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
    workflow = _normalise_workflow(ledger.get("workflow"))
    v_status = verification.get("status", "unknown")
    v_cmd = verification.get("last_command")
    py_files = verification.get("changed_py_files") or []
    updated_at = (ledger.get("meta") or {}).get("updated_at", "?")

    # Only inject when there is something useful to say.
    workflow_active = workflow.get("stage") not in (None, "idle")
    has_content = any(
        [goal, last_prompt, v_status != "unknown", py_files, workflow_active]
    )
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
    if workflow_active:
        parts.append(f"  Stage    : {workflow.get('stage')}")
    if workflow.get("plan_ref"):
        parts.append(f"  Plan ref : {workflow.get('plan_ref')}")
    if workflow.get("current_task"):
        parts.append(f"  Task     : {workflow.get('current_task')}")
    review = workflow.get("review") or {}
    if review.get("status") not in (None, "not_required"):
        parts.append(
            "  Review   : "
            + str(review.get("status"))
            + (f" via {review.get('mode')}" if review.get("mode") else "")
        )

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
