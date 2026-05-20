"""Phase 4 completion gate — Pillar 7 reminder + governor-paths matching.

Single source of truth for the Stop-hook completion-gate logic that
``.{claude,codex}/hooks/completion_gate.py`` previously duplicated.

Public surface (R0-A.3 — structured fields, rendering deferred to hooks):

* ``GOVERNOR_REMINDER_WITH_PR`` / ``GOVERNOR_REMINDER_NO_PR`` — frozen
  reminder templates, byte-for-byte equal across Claude / Codex.
* ``GateResult`` — frozen dataclass carrying ``status``, ``governor_changing``,
  ``pr``. Hook adapters render the reminder string from the result so
  that future fields (timestamps, file counts) can be added without
  reshaping the I/O contract.
* ``evaluate_gate(...)`` — pure decision function: takes ``state_dir``,
  ``changed_files``, and optional ``pr_number``; returns ``GateResult``.
* ``render_reminder(result)`` — maps ``GateResult`` to the reminder
  string, or ``None`` when silent.
* ``governor_changing_segment(state_dir, ...)`` — Hook-facing helper
  matching the pre-Phase-5 signature. Hooks may pass ``None`` to fall
  back to git/gh lookups, or supply pre-computed values for testing.
* ``parse_trigger_globs`` (IC-10), ``is_log_only_backfill`` (HC-4.5),
  ``is_governor_changing``, ``match_log_entry``, ``pr_number_from_branch``,
  ``changed_files_via_git`` — building blocks reused by hooks.

Behaviour invariance (HC-5.1): all bodies mirror the pre-Phase-5
implementations including the 2h commit fallback in
``changed_files_via_git`` and the `unknown`/`mismatch`/`missing`/`match`
classification semantics in ``match_log_entry``.
"""

from __future__ import annotations

import contextlib
import fnmatch
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .markers import MarkerLifecycle, read_latest_token
from .paths import GOVERNOR_PATHS_MD, REPO_ROOT
from .sync_cosmetic import DiffSource, governor_subset, is_sync_cosmetic_only
from .tokens import EXPLORATION_TOKENS

GOVERNOR_REVIEW_LOG_PREFIX = "docs/history/archive/governor-review-log/"

# IC-2: byte-for-byte string-equal between Claude/Codex hook adapters.
# Parity is asserted by tests/unit/agents_shared/test_completion_gate.py.
# AGENT_LOCALE rendering (issue #133) is applied at the hook's emit call
# site via governor.locale.get_locale_string; both hooks share the same
# resolver and these constants remain the English canonical, so byte
# equality (and the parity test) hold for the default locale.
GOVERNOR_REMINDER_WITH_PR = "\n".join(
    [
        "[completion-gate] Governor-changing changes detected (Pillar 7).",
        "PR #{pr} description must contain a `## Governor Footer` block.",
        "CI will lint via tools/check_governor_footer.py --require-governor-footer.",
        "See: docs/history/047-governor-review-provenance-consolidation.md (D2/D5).",
    ]
)

GOVERNOR_REMINDER_NO_PR = "\n".join(
    [
        "[completion-gate] Governor-changing changes detected (Pillar 7).",
        "PR number unknown — open the PR first, then fill the `## Governor Footer` block in its description.",
        "See: docs/history/047-governor-review-provenance-consolidation.md (D2/D5).",
    ]
)


# R1-A.2: closed Literal stops invalid-status drift if a future contributor
# returns a typo'd string from evaluate_gate or a custom branch.
GateStatus = Literal[
    "silent_no_changes",
    "silent_log_only",
    "silent_sync_cosmetic",
    "silent_exploration",
    "silent_not_governor",
    "match",
    "mismatch",
    "missing",
    "unknown",
]


@dataclass(frozen=True)
class GateResult:
    """Pillar 7 completion-gate evaluation result.

    ``status`` is one of the eight values declared in :data:`GateStatus`:

    * ``"silent_no_changes"`` — no changed files
    * ``"silent_log_only"`` — only governor-review-log/ paths changed (HC-4.5)
    * ``"silent_sync_cosmetic"`` — governor-matching subset is sync-cosmetic only (ADR 047 D4)
    * ``"silent_exploration"`` — exploration/탐색 marker present
    * ``"silent_not_governor"`` — no changed file matches governor globs
    * ``"match"`` — governor-changing + log entry pr-{pr}-*.md present
    * ``"mismatch"`` — log entry with different PR number
    * ``"missing"`` — governor-changing but no log entry
    * ``"unknown"`` — log entry exists but PR number unresolvable yet
    """

    status: GateStatus
    governor_changing: bool
    pr: int | None


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def parse_trigger_globs(md_path: Path = GOVERNOR_PATHS_MD) -> list[str]:
    """Extract Tier A/B/C glob patterns from governor-paths.md (IC-10)."""

    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return []
    globs: list[str] = []
    in_tier = False
    for line in text.splitlines():
        if re.match(r"^### Tier [ABC]", line):
            in_tier = True
            continue
        if in_tier and re.match(r"^##", line):
            in_tier = False
            continue
        if in_tier and line.strip().startswith("-"):
            m = re.search(r"`([^`]+)`", line)
            if m:
                globs.append(m.group(1))
    return globs


def _matches_glob(path: str, glob: str) -> bool:
    """Match a repo-relative path against a governor-paths.md glob pattern."""

    if "**" in glob:
        prefix = glob.split("**")[0]
        return path.startswith(prefix)
    return fnmatch.fnmatch(path, glob)


def is_log_only_backfill(changed: list[str]) -> bool:
    """True when ALL changed files live under ``governor-review-log/`` (HC-4.5)."""

    return bool(changed) and all(
        p.startswith(GOVERNOR_REVIEW_LOG_PREFIX) for p in changed
    )


def is_governor_changing(changed: list[str], globs: list[str]) -> bool:
    return any(_matches_glob(p, g) for p in changed for g in globs)


LogEntryStatus = Literal["match", "mismatch", "missing", "unknown"]


def match_log_entry(changed: list[str], current_pr: int | None) -> LogEntryStatus:
    """Classify governor-review-log entry presence vs the current PR number.

    Anchored at ``GOVERNOR_REVIEW_LOG_PREFIX``: a path is only treated as a
    log entry when it lives under the canonical archive location (currently
    ``docs/history/archive/governor-review-log/``). This prevents an
    accidental resurrection of the pre-#160 path
    (``docs/ai/shared/governor-review-log/...``) from silencing the
    completion gate via a "match" verdict — Codex round-2 R1.
    """

    pattern = re.escape(GOVERNOR_REVIEW_LOG_PREFIX) + r"pr-(\d+)-"
    log_entries = [p for p in changed if re.search(pattern, p)]
    if not log_entries:
        return "missing"
    if current_pr is None:
        return "unknown"
    for entry in log_entries:
        m = re.search(pattern, entry)
        if m and int(m.group(1)) == current_pr:
            return "match"
    return "mismatch"


def _run_git(*args: str, repo_root: Path = REPO_ROOT) -> str:
    result = subprocess.run(  # noqa: S603,S607 — fixed args
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def changed_files_via_git(repo_root: Path = REPO_ROOT) -> list[str]:
    """Uncommitted (staged + unstaged) + untracked files, with 2h commit fallback."""

    uncommitted = _run_git("diff", "--name-only", "HEAD", repo_root=repo_root)
    untracked = _run_git(
        "ls-files", "--others", "--exclude-standard", repo_root=repo_root
    )
    combined = sorted(
        {
            line
            for chunk in (uncommitted, untracked)
            for line in chunk.splitlines()
            if line
        }
    )
    if combined:
        return combined
    with contextlib.suppress(Exception):
        last_epoch = int(
            _run_git("log", "-1", "--format=%ct", repo_root=repo_root).strip() or "0"
        )
        if time.time() - last_epoch < 7200:
            last_commit = _run_git(
                "diff", "--name-only", "HEAD~1", "HEAD", repo_root=repo_root
            )
            return [line for line in last_commit.splitlines() if line]
    return []


def pr_number_from_branch() -> int | None:
    """Return current PR number via ``gh`` CLI, or ``None`` on any failure."""

    try:
        result = subprocess.run(  # noqa: S603,S607 — fixed args
            ["gh", "pr", "view", "--json", "number"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return int(data["number"])
    except Exception:  # noqa: BLE001,S110 — fail-open per HC-4.7
        pass
    return None


# ---------------------------------------------------------------------------
# Decision + rendering
# ---------------------------------------------------------------------------
def evaluate_gate(
    *,
    state_dir: Path,
    changed_files: list[str],
    pr_number: int | None,
    md_path: Path = GOVERNOR_PATHS_MD,
    diff_source: DiffSource | None = None,
) -> GateResult:
    """Pure Pillar 7 decision function — see ``GateResult`` for branches.

    ``diff_source`` is injected by tests for the ADR 047 D4 sync-cosmetic
    carve-out; production callers omit it and the carve-out reads diffs via
    ``git`` directly.
    """

    if not changed_files:
        return GateResult("silent_no_changes", False, pr_number)

    if is_log_only_backfill(changed_files):
        return GateResult("silent_log_only", False, pr_number)

    token = read_latest_token(state_dir, MarkerLifecycle.READ_ONLY)
    if token in EXPLORATION_TOKENS:
        return GateResult("silent_exploration", False, pr_number)

    globs = parse_trigger_globs(md_path)
    if not globs:
        return GateResult("silent_not_governor", False, pr_number)

    subset = governor_subset(changed_files, globs)
    if not subset:
        return GateResult("silent_not_governor", False, pr_number)

    if is_sync_cosmetic_only(subset, diff_source):
        return GateResult("silent_sync_cosmetic", False, pr_number)

    log_status = match_log_entry(changed_files, pr_number)
    return GateResult(log_status, True, pr_number)


def render_reminder(result: GateResult) -> str | None:
    """Map a ``GateResult`` to its reminder text, or ``None`` if silent.

    Silent for any ``status`` starting with ``"silent_"``, plus ``"match"``
    (log entry already present for the right PR) and ``"unknown"`` (PR
    number unresolvable — defer to next Stop event).
    """

    if not result.governor_changing:
        return None
    if result.status in ("match", "unknown"):
        return None
    if result.pr is None:
        return GOVERNOR_REMINDER_NO_PR
    return GOVERNOR_REMINDER_WITH_PR.format(pr=result.pr)


def governor_changing_segment(
    state_dir: Path,
    changed_files: list[str] | None = None,
    pr_number: int | None = None,
    md_path: Path = GOVERNOR_PATHS_MD,
) -> str | None:
    """Hook-facing wrapper combining evaluate_gate + render_reminder.

    Hooks may pass ``None`` for ``changed_files`` / ``pr_number`` to fall
    back to ``changed_files_via_git`` / ``pr_number_from_branch``, or
    supply pre-computed values for testing and tool-specific overrides
    (e.g. Codex ``_shared.changed_files()``).
    """

    if changed_files is None:
        changed_files = changed_files_via_git()
    if pr_number is None:
        pr_number = pr_number_from_branch()
    return render_reminder(
        evaluate_gate(
            state_dir=state_dir,
            changed_files=changed_files,
            pr_number=pr_number,
            md_path=md_path,
        )
    )
