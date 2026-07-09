"""Mid-task stage-gate policy (ADR 050, issue #268).

Single source of truth for:

* ``STAGE_GATE_REMINDER`` — canonical English advisory text; locale
  rendering happens at the hook's emit call site via
  ``governor.locale.get_locale_string`` (issue #133 pattern, ADR050-G4).
* ``GATED_STAGES`` — explicit allowlist of ledger stages that gate
  (ADR050-G2: unknown or missing stages stay silent, fail-open).
* ``read_ledger_stage(ledger_path)`` — best-effort ``workflow.stage``
  reader; any I/O or shape problem returns ``None``.
* ``is_implementation_source(file_path, repo_root)`` — ``.py`` under
  ``src/`` or ``examples/`` predicate (ADR050-G3 surface).
* ``should_stage_gate(payload, state_dir, ledger_path, repo_root)`` —
  pure decision; does not write markers.
* ``has_fired_this_session`` / ``mark_fired`` — once-per-session dedup
  markers (``stage-gate-*.json``) with the IC-11 24h defensive window.
  Markers are self-pruning on write; the Stop hook does not own them.

Fail-open contract (HC-5.5 / Plan §D3): every helper degrades to the
silent path on error. This module performs no network access and writes
only inside the ``state_dir`` it is handed.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
from pathlib import Path

from .markers import MarkerLifecycle, read_latest_token
from .paths import REPO_ROOT
from .time_window import _within_24h
from .tokens import PLAN_WAIVER_TOKENS

STAGE_GATE_REMINDER = "\n".join(
    [
        "[stage-gate] Implementation edit with no active plan in the work ledger.",
        "Mid-task capability discovery is new implementation-class work: stop,",
        "report the gap, and route to /plan-feature (Claude) or $plan-feature (Codex)",
        "before continuing (AGENTS.md § Mid-Task Scope Expansion, ADR 050).",
        "For a small self-evident change or urgent fix, silence this with a",
        "[trivial] / [hotfix] token on your next prompt.",
        "Advisory only — fires at most once per session.",
    ]
)

# ADR 054: shown when an implementation edit is attempted while the ledger
# stage is `planned` (a plan exists but `/execute-plan` has not been invoked).
# Canonical English source; locale-rendered at the hook emit site (ADR050-G4).
# Neutral wording: on Claude the PreToolUse hook prefixes a [BLOCKED] cue and
# exits 2 (hard block); on Codex it is a Stop-time advisory segment.
PLAN_EXECUTE_REMINDER = "\n".join(
    [
        "[stage-gate] Implementation edit while the work ledger stage is 'planned'.",
        "An approved plan exists but execution has not formally started via",
        "/execute-plan (Claude) or $execute-plan (Codex). Invoke it to begin — it",
        "advances the ledger to 'executing'. For a small self-evident change or",
        "urgent fix, use a [trivial] / [hotfix] token on your next prompt instead.",
        "(AGENTS.md § Plan→Execute Boundary, ADR 054)",
    ]
)

# ADR050-G2: allowlist of stages that positively mean "no active plan".
# Active stages (planned/executing/reviewing), unknown strings, and a
# missing/unreadable ledger all stay silent.
GATED_STAGES: frozenset[str] = frozenset({"idle", "complete", "blocked"})

# ADR054-G2: disjoint sibling of GATED_STAGES. `planned` means a plan exists
# in the ledger but `/execute-plan` has not been invoked; an implementation
# edit here is gated separately from the "no plan at all" case above. The two
# sets never overlap — a stage falls in at most one.
PLAN_EXECUTE_GATED_STAGES: frozenset[str] = frozenset({"planned"})

# ADR050-G3: implementation surface. Widening this tuple re-enters ADR 050.
IMPLEMENTATION_PREFIXES: tuple[str, ...] = ("src", "examples")

_MARKER_PREFIX = "stage-gate-"
_SESSION_ID_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def default_ledger_path(state_root: Path) -> Path:
    """Ledger location under a state root (mirrors ``work_ledger`` layout)."""

    return state_root / ".agents" / "state" / "current-work.json"


def read_ledger_stage(ledger_path: Path) -> str | None:
    """Return ``workflow.stage`` from the work ledger, or ``None``.

    Missing file, unreadable JSON, or an unexpected shape all return
    ``None`` — the gate only acts on positive evidence (ADR050-G2).
    """

    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        return None
    stage = workflow.get("stage")
    return stage if isinstance(stage, str) else None


def is_implementation_source(
    file_path: str | None, repo_root: Path = REPO_ROOT
) -> bool:
    """True iff ``file_path`` is a ``.py`` file under ``src/`` or ``examples/``.

    Accepts absolute paths and repo-relative paths; both are normalised
    against ``repo_root`` (R1.2 — ``src/../tests/foo.py`` resolves to
    ``tests/`` and does not gate). Paths outside the repo return ``False``.
    """

    if not file_path or not file_path.endswith(".py"):
        return False
    try:
        root = repo_root.resolve()
        candidate = Path(file_path)
        resolved = (
            candidate.resolve()
            if candidate.is_absolute()
            else (root / candidate).resolve()
        )
        rel = resolved.relative_to(root)
    except (ValueError, OSError):
        return False
    parts = rel.parts
    return bool(parts) and parts[0] in IMPLEMENTATION_PREFIXES


def _session_marker_name(session_id: str) -> str:
    safe = _SESSION_ID_SAFE.sub("_", session_id)[:64] or "unknown"
    return f"{_MARKER_PREFIX}{safe}.json"


def has_fired_this_session(state_dir: Path, session_id: str) -> bool:
    """True iff a stage-gate marker for this session exists within 24h."""

    marker = state_dir / _session_marker_name(session_id)
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    ts = data.get("ts") if isinstance(data, dict) else None
    return isinstance(ts, str) and _within_24h(ts)


def mark_fired(state_dir: Path, session_id: str) -> Path | None:
    """Claim the once-per-session marker; prune stale stage-gate markers.

    Pruning removes ``stage-gate-*.json`` files whose ``ts`` is missing,
    unreadable, or older than 24h — this module owns its own marker
    namespace (the Stop hook only consumes ``exception-token-*`` files).

    The claim uses exclusive create (R1.3): when a fresh marker for this
    session already exists, another writer won the race and this call
    returns ``None``. Callers must emit the advisory only on a non-``None``
    return, so concurrent hook invocations produce exactly one reminder.
    ``None`` is also returned on any write failure (fail-open).
    """

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    for stale in state_dir.glob(f"{_MARKER_PREFIX}*.json"):
        keep = False
        with contextlib.suppress(OSError, json.JSONDecodeError, ValueError):
            data = json.loads(stale.read_text(encoding="utf-8"))
            ts = data.get("ts") if isinstance(data, dict) else None
            keep = isinstance(ts, str) and _within_24h(ts)
        if not keep:
            with contextlib.suppress(OSError):
                stale.unlink()

    marker = state_dir / _session_marker_name(session_id)
    record = {
        "session_id": session_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        # "x" = exclusive create — FileExistsError means a concurrent
        # writer claimed the session first (fresh markers survive pruning).
        with marker.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False))
    except OSError:  # includes FileExistsError
        return None
    return marker


def extract_session_id(payload: dict) -> str:
    """Return the hook payload's ``session_id`` (or ``"unknown"``)."""

    session_id = payload.get("session_id")
    return session_id if isinstance(session_id, str) and session_id else "unknown"


def should_stage_gate(
    payload: dict,
    state_dir: Path,
    ledger_path: Path,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Pure stage-gate decision for a PostToolUse Edit|Write payload.

    True iff ALL of:
      1. the edited file is a ``.py`` under ``src/`` or ``examples/``;
      2. the ledger stage is positively in ``GATED_STAGES``;
      3. no *plan-waiver* token marker is active (R1.1 — ``[trivial]`` /
         ``[hotfix]`` license implementation edits without a fresh plan;
         ``[exploration]`` declares a read-only session and does NOT
         suppress the gate — READ_ONLY, IC-11 24h window);
      4. the reminder has not already fired for this session.

    Marker writing is the caller's job (``mark_fired``) so this function
    stays side-effect free for tests.
    """

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not is_implementation_source(
        file_path if isinstance(file_path, str) else None, repo_root
    ):
        return False

    stage = read_ledger_stage(ledger_path)
    if stage not in GATED_STAGES:
        return False

    if read_latest_token(state_dir, MarkerLifecycle.READ_ONLY) in PLAN_WAIVER_TOKENS:
        return False

    return not has_fired_this_session(state_dir, extract_session_id(payload))


def _plan_execute_core(
    payload: dict,
    state_dir: Path,
    ledger_path: Path,
    repo_root: Path,
) -> bool:
    """Shared predicate for the plan→execute boundary (ADR 054).

    True iff ALL of:
      1. the edited file is a ``.py`` under ``src/`` or ``examples/``;
      2. the ledger stage is positively in ``PLAN_EXECUTE_GATED_STAGES``
         (``planned`` — a plan exists but ``/execute-plan`` has not run);
      3. no *plan-waiver* token marker is active (``[trivial]``/``[hotfix]``;
         ``[exploration]`` does NOT suppress — it implies no committed plan).

    Deliberately carries NO once-per-session term: callers layer dedup on only
    where an advisory budget applies (Codex Stop), never on the Claude block
    (ADR054-G1 D5 — a once-fired block would let the retry through).
    """

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not is_implementation_source(
        file_path if isinstance(file_path, str) else None, repo_root
    ):
        return False

    if read_ledger_stage(ledger_path) not in PLAN_EXECUTE_GATED_STAGES:
        return False

    return (
        read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)
        not in PLAN_WAIVER_TOKENS
    )


def should_block_plan_execute_edit(
    payload: dict,
    state_dir: Path,
    ledger_path: Path,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Claude ``PreToolUse`` hard-block decision (ADR 054, ADR054-G1).

    True iff an implementation-source ``Edit``/``Write`` is attempted while the
    ledger stage is ``planned`` and no plan-waiver token is active. No session
    dedup — the block holds on every edit until ``/execute-plan`` advances the
    stage to ``executing`` (ADR054-G1 D5). Fail-open (exit-0 allow on error) is
    the calling hook's job; this pure decision never raises for well-formed
    input and is side-effect free for tests.
    """

    return _plan_execute_core(payload, state_dir, ledger_path, repo_root)


def should_plan_execute_gate(
    payload: dict,
    state_dir: Path,
    ledger_path: Path,
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Codex Stop-time advisory decision (ADR 054 D8).

    Same core predicate as ``should_block_plan_execute_edit`` plus the
    once-per-session dedup the advisory channel uses (mirrors
    ``should_stage_gate``). Marker writing stays the caller's job
    (``mark_fired``) so this function is side-effect free for tests.
    """

    if not _plan_execute_core(payload, state_dir, ledger_path, repo_root):
        return False
    return not has_fired_this_session(state_dir, extract_session_id(payload))
