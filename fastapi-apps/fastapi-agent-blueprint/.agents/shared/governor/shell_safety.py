"""Shell command safety rules for PreToolUse hooks (Codex-side).

``check_bash_command`` is the single source of truth for the inline shell
command patterns that were previously declared directly in
``.codex/hooks/pre-tool-security.py`` (Phase 5 / PR-A.4 cleanup).

Public API:
  ``BASH_COMMAND_RULES`` — list of ``(compiled_pattern, deny_reason)`` pairs
  ``check_bash_command(command) -> str | None`` — the single hook entry point.
    Returns the deny reason string when the command matches a rule, ``None`` when safe.

Boundary: shell-level pattern detection only. The compound
infrastructure-import check (which needs both a regex match *and* a
path fragment test) is handled inside ``check_bash_command`` rather than
folded into ``BASH_COMMAND_RULES`` because it requires two conditions.
"""

from __future__ import annotations

import re

BASH_COMMAND_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+reset\s+--hard\b|\bgit\s+checkout\s+--\b"),
        "Destructive git rollback is forbidden in this repository.",
    ),
    (
        re.compile(r"\brm\s+-rf\b|\bdd\s+if=|\bmkfs\b"),
        "Destructive filesystem commands require explicit user approval and exact scope.",
    ),
    (
        re.compile(r"text\s*\(\s*f[\"']"),
        "Potential SQL injection pattern detected in shell-written code.",
    ),
    (
        re.compile(
            r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']{3,}[\"']",
            re.IGNORECASE,
        ),
        "Possible hardcoded secret detected in shell-written content.",
    ),
]

# Compound rule kept separate: matches only when *both* conditions hold.
_INFRA_IMPORT_PATTERN = re.compile(r"from\s+src\..*\.infrastructure")
_INFRA_DENY_REASON = "Domain layer must not import Infrastructure directly."


def check_bash_command(command: str) -> str | None:
    """Return a deny reason when *command* matches a safety rule, else ``None``.

    Call with the raw ``tool_input.command`` string from the PreToolUse payload.
    """
    for pattern, reason in BASH_COMMAND_RULES:
        if pattern.search(command):
            return reason
    if _INFRA_IMPORT_PATTERN.search(command) and "/domain/" in command:
        return _INFRA_DENY_REASON
    return None
