"""ADR 047 D4 — `/sync-guidelines` cosmetic edit detection for the completion gate.

The original ADR 045 governor classified any change under ``.claude/rules/**`` as
governor-changing. After ADR 047, three specific files routinely receive
timestamp-only or table-row-only edits as the closing ``/sync-guidelines`` step
on otherwise-non-governor PRs (the "self-loop" pulled feature PRs into
governor-changing classification purely because of their closure step). This
module recognises those cosmetic patterns and lets the completion gate skip
classification when the **governor-matching subset** of changed files is
limited to cosmetic edits.

Design (codex design review R5):
    The check operates on the *governor-matching subset* of changed files —
    paths that already matched a Tier A/B/C glob — not on the entire change
    set. So a PR that touches ``src/user/...`` (non-governor) plus
    ``.claude/rules/project-status.md`` `Last synced:` line still has the
    full src/ change unevaluated by this carve-out, but the governor-matching
    subset (``[project-status.md]``) classifies as cosmetic and the gate
    silences. By contrast, a PR that touches ``AGENTS.md`` plus the same
    cosmetic line has governor-matching subset
    ``[AGENTS.md, project-status.md]``, and AGENTS.md is not in the cosmetic
    set, so the gate triggers.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable

from .paths import REPO_ROOT

# Files whose `/sync-guidelines` cosmetic edits are exempt. Order matches the
# Exclusions list in `docs/ai/shared/governor-paths.md` (ADR 047 D4).
SYNC_COSMETIC_FILES: frozenset[str] = frozenset(
    {
        ".claude/rules/project-status.md",
        ".claude/rules/project-overview.md",
        ".claude/rules/commands.md",
    }
)

# `> Last synced:` blockquote line only.
_LAST_SYNCED_LINE_RE = re.compile(r"^>\s*Last synced:")
# Markdown table row line. Combined with the file-specific cosmetic patterns
# below, we accept these only inside `project-status.md` (where the
# `## Recent Major Changes` table lives).
_TABLE_ROW_RE = re.compile(r"^\|\s*[A-Za-z0-9`]")
# Markdown table header / separator lines (added or removed when the table is
# regenerated). Accepted as cosmetic for `project-status.md`.
_TABLE_HEADER_OR_SEP_RE = re.compile(r"^\|[-\s|:]+\|$|^\|\s*[A-Za-z][^|]*\|")

DiffSource = Callable[[str], str]


def _git_diff_for_path(path: str) -> str:
    """Default diff source — runs ``git diff origin/main..HEAD -- <path>``.

    Falls back to ``git diff -- <path>`` if the comparison ref is unavailable
    (e.g. fresh branch with no remote, detached HEAD, no origin remote). Empty
    string is returned on any subprocess failure so callers can treat
    diff-source failure as "do not exempt" rather than crashing.
    """

    git = shutil.which("git")
    if git is None:
        return ""
    for command in (
        [git, "-C", str(REPO_ROOT), "diff", "origin/main..HEAD", "--", path],
        [git, "-C", str(REPO_ROOT), "diff", "--cached", "--", path],
        [git, "-C", str(REPO_ROOT), "diff", "--", path],
    ):
        try:
            result = subprocess.run(  # noqa: S603 — git resolved via shutil.which, args fixed
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout:
            return result.stdout
    return ""


def _changed_lines(diff_text: str) -> list[str]:
    """Extract added/removed content lines from a unified diff (no headers)."""

    out: list[str] = []
    for line in diff_text.splitlines():
        if not line:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            continue
        if line[0] in ("+", "-"):
            out.append(line[1:])
    return out


def _is_cosmetic_diff(path: str, diff_text: str) -> bool:
    """Return True iff every changed line in the diff matches the cosmetic
    patterns allowed for the file at ``path``.

    Empty diffs (no changes) are treated as cosmetic — no semantic risk.
    """

    if path not in SYNC_COSMETIC_FILES:
        return False
    changed = _changed_lines(diff_text)
    if not changed:
        return True

    if path == ".claude/rules/project-status.md":
        return all(
            _LAST_SYNCED_LINE_RE.match(line)
            or _TABLE_ROW_RE.match(line)
            or _TABLE_HEADER_OR_SEP_RE.match(line)
            for line in changed
        )
    # project-overview.md, commands.md — `Last synced:` line only.
    return all(_LAST_SYNCED_LINE_RE.match(line) for line in changed)


def is_sync_cosmetic_only(
    governor_subset: list[str],
    diff_source: DiffSource | None = None,
) -> bool:
    """Return True iff every path in ``governor_subset`` is sync-cosmetic only.

    ``governor_subset`` is the subset of changed files that already match a
    Tier A/B/C glob. The caller (``evaluate_gate``) is responsible for
    computing the subset; this function does NOT inspect non-governor files.

    ``diff_source`` may be injected for testing; defaults to running
    ``git diff origin/main..HEAD -- <path>`` per file and falling through to
    cached / working-tree diff when needed.
    """

    if not governor_subset:
        return False
    source: DiffSource = diff_source if diff_source is not None else _git_diff_for_path
    for path in governor_subset:
        if path not in SYNC_COSMETIC_FILES:
            return False
        diff_text = source(path)
        if not _is_cosmetic_diff(path, diff_text):
            return False
    return True


def governor_subset(changed_files: list[str], globs: list[str]) -> list[str]:
    """Return the subset of ``changed_files`` that matches any governor glob."""

    from .completion_gate import _matches_glob  # local import to avoid cycle

    return [p for p in changed_files if any(_matches_glob(p, g) for g in globs)]


__all__ = [
    "SYNC_COSMETIC_FILES",
    "DiffSource",
    "_git_diff_for_path",
    "_is_cosmetic_diff",
    "_changed_lines",
    "governor_subset",
    "is_sync_cosmetic_only",
]
