"""Shared work ledger — cross-session context persistence.

Keeps the current work context alive across sessions so Claude, Codex, and
Antigravity can resume without losing scope, plan, or verification state.

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

Which ledger
------------
The module-level paths below come from this file's location, which names the
checkout whose code is *running*. A hook can run one checkout's copy for
another checkout's session (Claude Code desktop runs a worktree session's hooks
from the main checkout), so the hook-facing functions take ``state_root`` /
``repo_root`` from ``governor.resolve_session_roots`` (#425). ``None`` keeps the
module defaults — skills run from the session's own tree and pass nothing.

Design constraints
------------------
- All public functions are fail-open: I/O errors return None / empty safely.
- No top-level side effects — callers drive all reads and writes.
- IC-14: no governor policy inline — this module owns only ledger I/O.
- Writes are atomic (ADR052-G4): the new ledger is written beside the old one
  and swapped in with ``os.replace``, so a reader gets one or the other, never
  a partial file.
- Updates are serialised (ADR052-G4): each update helper holds an exclusive
  ``flock`` on ``current-work.json.lock`` from its read to its write, so two
  hooks or two sessions in one tree cannot lose each other's updates. An update
  that cannot take the lock is dropped: another writer held it for
  ``_LOCK_TIMEOUT_S``, or this caller could not open the lock file or was
  refused ``flock`` — none of which shows that nobody else holds it, so writing
  anyway could undo another writer's update. Only where nobody can lock at all
  (no ``fcntl``, or a filesystem without ``flock`` for this file) do updates
  run unlocked, as they all did before.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from collections.abc import Callable
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

# An update holds the ledger lock for well under a millisecond, so a wait this
# long means a stuck holder, and a hook must not hang on one. Waiters poll,
# backing off to _LOCK_POLL_MAX_S between attempts.
_LOCK_TIMEOUT_S = 2.0
_LOCK_POLL_MAX_S = 0.025
# How a refused flock reads. Busy: another writer holds it — EACCES too, which
# is how fcntl(F_SETLK) reports a conflict where Python emulates flock with it.
# Unsupported: the filesystem has no flock for this file, for any caller, so
# nobody can hold the lock and the update runs unlocked. Anything else — EPERM
# or ENOSYS (a sandbox denying this caller), ENOLCK (lock table full, or a
# remote lock manager failed), EINVAL — says nothing about other writers: the
# update is dropped.
_LOCK_BUSY = frozenset({errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES})
_LOCK_UNSUPPORTED = frozenset({errno.ENOTSUP, errno.EOPNOTSUPP})

# Harness-generated turns reach UserPromptSubmit like typed prompts (#425):
# Claude Code delivers a finished background task as <task-notification> and a
# side-session status update as <system-reminder>. A prompt made of nothing but
# such blocks is not the operator's, and storing it overwrote the prompt that
# SessionStart shows as "Last msg". Text outside the blocks keeps the prompt —
# a child session's first message is a reminder block followed by its task.
_HARNESS_ENVELOPE = re.compile(
    r"<(task-notification|system-reminder)>.*?</\1>", re.DOTALL
)


def _is_harness_notification(prompt: str) -> bool:
    stripped = prompt.strip()
    # Cheap exit for every typed prompt: an envelope-only one starts with "<".
    return stripped.startswith("<") and not _HARNESS_ENVELOPE.sub("", stripped).strip()


def _paths(state_root: Path | None) -> tuple[Path, Path]:
    """``(state dir, ledger path)`` under ``state_root``, else the module defaults."""

    if state_root is None:
        return STATE_DIR, LEDGER_PATH
    state_dir = state_root / ".agents" / "state"
    return state_dir, state_dir / "current-work.json"


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


def read_ledger(*, state_root: Path | None = None) -> dict | None:
    """Return the current ledger, or None if absent / unreadable."""
    with contextlib.suppress(Exception):
        text = _paths(state_root)[1].read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return _migrate_ledger(data)
    return None


def write_ledger(
    data: dict, updated_by: str = "system", *, state_root: Path | None = None
) -> bool:
    """Persist the ledger atomically. Returns True on success.

    A blind write: it replaces whatever is there. Changing part of the ledger is
    ``_update_ledger``'s job, which holds the lock across the read as well.
    """
    with contextlib.suppress(Exception):
        data = _migrate_ledger(data) or data
        data["schema_version"] = SCHEMA_VERSION
        data.setdefault("meta", {})
        data["meta"]["updated_at"] = _now_iso()
        data["meta"]["updated_by"] = updated_by
        state_dir, ledger_path = _paths(state_root)
        state_dir.mkdir(parents=True, exist_ok=True)
        _replace_file(ledger_path, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    return False


def _replace_file(path: Path, text: str) -> None:
    """Write ``text`` to a temporary file beside ``path``, then swap it in.

    ``write_text`` truncates first and writes after, and a reader in between gets
    an empty or half-written file. Here that is not harmless: ``read_ledger``
    turns it into ``None``, and that reader's own update then writes a default
    ledger back over everything. ``os.replace`` is atomic, so a reader opens the
    old file or the new one. No ``fsync``: the race is between processes, which
    share the page cache, and crash durability is not a goal.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _lock_ledger(ledger_path: Path) -> int | None:
    """Take the ledger lock: an exclusive ``flock`` on a file beside the ledger.

    Returns the descriptor whose ``os.close`` releases the lock, or ``None``
    when nobody can lock this file (no ``fcntl``, or a filesystem without
    ``flock``) and the update has to run unlocked. Raises ``TimeoutError`` when
    another writer holds the lock past ``_LOCK_TIMEOUT_S``, and passes on any
    other error from opening the lock file or from ``flock``: what this caller
    cannot do says nothing about whether another writer holds the lock.

    Not the ledger itself: ``os.replace`` gives the ledger a new inode on every
    write, and a lock on the old inode excludes nobody. ``flock``, not
    ``lockf``: it belongs to the open file description, so it also excludes a
    second descriptor in this process, and closing an unrelated descriptor for
    the same file does not drop it. The lock file is never deleted — a writer
    could still hold the unlinked inode while the next one locks a new file.
    """
    try:
        import fcntl
    except ImportError:  # not POSIX: no process here can take this lock either
        return None
    # First use creates the state directory here, before anything is written,
    # so even the very first updates are serialised.
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        ledger_path.with_name(ledger_path.name + ".lock"),
        os.O_RDWR | os.O_CREAT,
        0o644,
    )
    deadline = time.monotonic() + _LOCK_TIMEOUT_S
    delay = 0.001
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError as exc:
            busy = exc.errno in _LOCK_BUSY
            if busy and time.monotonic() < deadline:
                time.sleep(delay)
                delay = min(delay * 2, _LOCK_POLL_MAX_S)
                continue
            os.close(fd)
            if exc.errno in _LOCK_UNSUPPORTED:
                return None
            if busy:
                raise TimeoutError("another writer holds the ledger lock") from None
            raise


def _update_ledger(
    change: Callable[[dict], None], *, updated_by: str, state_root: Path | None
) -> bool:
    """Apply ``change`` to the ledger and write it back, under the ledger lock.

    Every update helper goes through here, so no two updates — in one process
    or in two — can read the same ledger and have the second write throw away
    the first one's change. Returns whether the ledger was written. An update
    that cannot take the lock is dropped, not applied unlocked: after a timeout
    the holder is still running, and its write would land on top of ours or
    ours on top of its; after any other lock error nothing shows that no one
    else holds it. If ``change`` raises, nothing is written and the lock is
    still released. Not reentrant: a nested call would time out on its own lock.
    """
    try:
        lock = _lock_ledger(_paths(state_root)[1])
    except OSError:  # TimeoutError included
        return False
    try:
        ledger = read_ledger(state_root=state_root) or _default_ledger()
        change(ledger)
        return write_ledger(ledger, updated_by=updated_by, state_root=state_root)
    finally:
        if lock is not None:
            with contextlib.suppress(OSError):
                os.close(lock)


def _changed_py_files(repo_root: Path | None = None) -> list[str]:
    """Collect uncommitted/untracked .py files (fail-open)."""
    with contextlib.suppress(Exception):
        cwd = repo_root or REPO_ROOT
        tracked = subprocess.run(  # noqa: S603,S607
            ["git", "diff", "--name-only", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        untracked = subprocess.run(  # noqa: S603,S607
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd,
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


def update_last_prompt(
    prompt: str, session_id: str | None = None, *, state_root: Path | None = None
) -> None:
    """Store the latest prompt text (truncated). Called from UserPromptSubmit.

    A harness notification is not a prompt: it leaves the ledger untouched.
    """
    if _is_harness_notification(prompt):
        return

    def record_prompt(ledger: dict) -> None:
        ledger["last_prompt"] = prompt[:_PROMPT_MAX_CHARS] if prompt else None
        if session_id:
            ledger.setdefault("meta", {})["session_id"] = session_id

    _update_ledger(
        record_prompt, updated_by="hook:user_prompt_submit", state_root=state_root
    )


def update_verification_from_git(
    *, repo_root: Path | None = None, state_root: Path | None = None
) -> None:
    """Refresh changed_py_files from git. Called from Stop hook."""
    # Asked before the lock is taken: the answer does not depend on the ledger,
    # and no other update should wait behind a subprocess.
    py_files = _changed_py_files(repo_root)

    def record_changed_files(ledger: dict) -> None:
        verification = ledger.setdefault("verification", {})
        verification["changed_py_files"] = py_files
        # Promote status to "pending" only when files exist and status was unknown.
        if py_files and verification.get("status") == "unknown":
            verification["status"] = "pending"

    _update_ledger(record_changed_files, updated_by="hook:stop", state_root=state_root)


def update_goal_scope_plan(
    goal: str | None = None,
    scope: str | None = None,
    plan: str | None = None,
    updated_by: str = "skill",
) -> None:
    """Set goal / scope / plan fields. Called from plan-feature, new-domain, etc."""

    def set_fields(ledger: dict) -> None:
        if goal is not None:
            ledger["goal"] = goal
        if scope is not None:
            ledger["scope"] = scope
        if plan is not None:
            ledger["plan"] = plan

    _update_ledger(set_fields, updated_by=updated_by, state_root=None)


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

    def set_workflow(ledger: dict) -> None:
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

    _update_ledger(set_workflow, updated_by=updated_by, state_root=None)


def _is_shell_control_token(token: str) -> bool:
    """Return True for a shlex punctuation token that sequences, pipes or backgrounds.

    ``shlex`` groups adjacent operator characters, so ``|&``, ``&|`` and ``;;``
    arrive as single tokens; any token carrying ``|`` or ``;`` is rejected, as is
    an ``&`` run without a redirection. Pure redirections such as ``2>&1`` keep
    the command's own exit status and stay allowed; plain ``>``/``>>`` output
    redirection stays rejected as before.
    """
    if not token or set(token) - set(";&|<>"):
        return False
    if token in {">", ">>"} or "|" in token or ";" in token:
        return True
    return not set(token) & set("<>")


def is_verification_command(command: str) -> bool:
    """Recognize simple verify invocations without creating command-log state.

    Shell control operators are excluded: a composite command's exit code may
    describe a later echo/fallback instead of the verification. Unknown forms
    remain unrecorded rather than manufacturing a passing result.
    """
    try:
        if "\n" in command or "\r" in command:
            return False
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        args = list(lexer)
    except ValueError:
        return False
    if any(_is_shell_control_token(part) for part in args):
        return False
    if args[:2] == ["uv", "run"]:
        args = args[2:]
    if not args:
        return False
    inspection_flags = {"--help", "-h", "--version", "-V", "--collect-only", "--co"}
    if any(arg.split("=", 1)[0] in inspection_flags for arg in args[1:]):
        return False
    executable = Path(args[0]).name
    if executable in {"pytest", "pyright", "pre-commit"}:
        return executable != "pre-commit" or args[1:2] == ["run"]
    if executable in {"python", "python3"}:
        return args[1:3] == ["-m", "pytest"]
    if executable == "make":
        return args[1:2] in [["test"], ["demo"], ["demo-rag"], ["check-core"]]
    return executable == "alembic" and args[1:2] == ["upgrade"]


def mark_verified(
    command: str, passed: bool, *, state_root: Path | None = None
) -> None:
    """Record a verify-command result. Called from verify-aware hooks/skills."""

    def record_result(ledger: dict) -> None:
        verification = ledger.setdefault("verification", {})
        verification["status"] = "passed" if passed else "failed"
        verification["last_verified_at"] = _now_iso()
        verification["last_command"] = command
        # Clear pending py_files on pass.
        if passed:
            verification["changed_py_files"] = []

    _update_ledger(record_result, updated_by="hook:verify", state_root=state_root)


def build_workflow_advisory_segments(
    *,
    changed_files: list[str],
    governor_changing: bool,
    state_root: Path | None = None,
) -> list[str]:
    """Return advisory-only native workflow reminders for Stop hooks.

    The helper is intentionally non-blocking. It records missing workflow
    state as guidance, while CI and future hardening PRs decide which
    high-confidence conditions become hard gates.
    """

    with contextlib.suppress(Exception):
        if not changed_files:
            return []
        ledger = read_ledger(state_root=state_root) or _default_ledger()
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


def build_session_summary(*, state_root: Path | None = None) -> str | None:
    """Return a one-paragraph context summary for SessionStart injection.

    Returns None when no ledger exists or ledger contains no meaningful state
    (all of goal/last_prompt/verification are unset/unknown).
    """
    ledger = read_ledger(state_root=state_root)
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

    # Completed cache is not a request to resume old work. Preserve unresolved
    # verification/review/blockers even if a caller marked the workflow complete.
    if (
        workflow.get("stage") == "complete"
        and not py_files
        and v_status not in {"pending", "failed"}
        and not blockers
        and (workflow.get("review") or {}).get("status")
        in {None, "not_required", "complete"}
    ):
        return None

    # Only inject when there is something useful to say.
    workflow_active = workflow.get("stage") not in (None, "idle")
    has_content = any(
        [goal, last_prompt, v_status != "unknown", py_files, workflow_active]
    )
    if not has_content:
        return None

    parts.append(
        f"[work-ledger] Previous work (local cache) — last updated {updated_at}"
    )
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
