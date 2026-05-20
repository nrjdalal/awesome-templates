"""Shared sync-advisory classification (PR-A.5 + F-1).

Single source of truth for ``FOUNDATION_PREFIXES`` / ``STRUCTURE_MARKERS``
and the ``classify_advisory`` decision function. Both the Codex Python hook
(``.codex/hooks/stop-sync-reminder.py``) and the Claude bash hook
(``.claude/hooks/stop-sync-reminder.sh``) delegate here via thin shims,
satisfying IC-2 (single SOT) and IC-14 (no inline policy redeclaration).

The bash hook uses ``governor.sync_advisory_cli`` (same package) as its
bridge, with a fail-open inline-grep fallback for environments where Python
is unavailable (HC-5.5).

Semantic note — primary vs fallback matching:
  This module uses ``str.startswith`` prefix matching. The bash fallback
  (inactive under normal conditions) uses anchored ``grep -E`` patterns.
  Paths like ``pyproject.toml.bak`` would match the Python path but not
  the bash fallback. Such paths are not produced by normal git operations,
  so the divergence is accepted and confined to the fallback-only path.
"""

from __future__ import annotations

from typing import Literal

FOUNDATION_PREFIXES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    ".codex/",
    ".agents/",
    ".claude/hooks/",
    ".claude/rules/",
    ".claude/settings.json",
    "docs/ai/shared/",
    # "docs/ai/shared/skills/" omitted — already covered by "docs/ai/shared/"
    # prefix via str.startswith; keeping it would be a redundant entry.
    "src/_apps/",
    "src/_core/",
    "pyproject.toml",
    ".pre-commit-config.yaml",
)

STRUCTURE_MARKERS: tuple[str, ...] = (
    "/infrastructure/di/",
    "/interface/server/routers/",
    "/domain/protocols/",
    "/domain/dtos/",
)

AdvisoryLevel = Literal["foundation", "structure", None]


def classify_advisory(
    changed_files: list[str],
) -> tuple[AdvisoryLevel, list[str]]:
    """Classify the advisory level for a set of changed file paths.

    Returns a ``(level, matching_files)`` pair:
      - ``("foundation", [...])`` — one or more foundation files changed;
        guideline sync is required before closing the work.
      - ``("structure", [...])`` — domain-structure files changed but no
        foundation files; guideline sync is recommended.
      - ``(None, [])`` — no advisory needed.

    Foundation takes precedence over structure when both are present.
    """
    foundation = [p for p in changed_files if p.startswith(FOUNDATION_PREFIXES)]
    if foundation:
        return "foundation", foundation

    structure = [
        p
        for p in changed_files
        if p.startswith("src/")
        and "/_" not in p
        and any(marker in p for marker in STRUCTURE_MARKERS)
    ]
    if structure:
        return "structure", structure

    return None, []
