"""Codex-side safety check + single-entry safe parser (HC-1).

The Codex ``user-prompt-submit`` hook must run safety checks **before**
the exception-token parser so dangerous prompts cannot produce a marker
even when prefixed with ``[trivial]``. Phase 5 collapses that ordering
into a single entry point ``safe_parse_exception_token`` so hook shims
cannot accidentally invoke the parser without a safety check first
(R0-C.1 — callable-injection rejected as bypass-prone).

Public API:

* ``PROMPT_RULES`` — list of (pattern, reason, additional context).
  Mirrors the pre-Phase-5 Codex rule set verbatim.
* ``check_safety(prompt) -> Blocked | None`` — internal helper.
* ``safe_parse_exception_token(prompt) -> SafeParseResult`` — the
  single Codex entry point. Returns ``Blocked`` (parser was *not*
  invoked) or ``ParsedToken`` (decision payload identical to the
  Claude-side ``parse_exception_token`` output).

Boundary: this module owns the *policy*. Stdout/stderr emission and
hook-payload framing remain in the Codex hook adapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tokens import parse_exception_token

PROMPT_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"(ignore|disable|bypass).*(AGENTS\.md|CLAUDE\.md|hooks?|sandbox|approval|rules?)",
            re.IGNORECASE,
        ),
        "Rule-bypass request detected.",
        "Do not bypass repository rules or Codex safety controls. Ask for a scoped goal instead.",
    ),
    (
        re.compile(r"\bgit\s+reset\s+--hard\b|\bgit\s+checkout\s+--\b", re.IGNORECASE),
        "Destructive git command requested.",
        "This repository does not allow destructive git rollback without explicit confirmation and scope.",
    ),
    (
        re.compile(r"\brm\s+-rf\b|\bdd\s+if=|\bmkfs\b", re.IGNORECASE),
        "Destructive shell command requested.",
        "Ask the user to confirm the exact path or target before any destructive command is considered.",
    ),
]


@dataclass(frozen=True)
class Blocked:
    """Safety rule matched. The parser was not invoked."""

    reason: str
    additional_context: str


@dataclass(frozen=True)
class ParsedToken:
    """Safety passed. ``payload`` mirrors ``parse_exception_token`` output."""

    payload: dict


SafeParseResult = Blocked | ParsedToken


def check_safety(prompt: str) -> Blocked | None:
    """Return ``Blocked`` on the first matching safety rule, else ``None``."""

    for pattern, reason, extra in PROMPT_RULES:
        if pattern.search(prompt):
            return Blocked(reason=reason, additional_context=extra)
    return None


def safe_parse_exception_token(prompt: str) -> SafeParseResult:
    """Single Codex entry point — safety first, then token parser.

    Hook shims must call this rather than ``parse_exception_token``
    directly. The ordering invariant (HC-1: safety-block-first → parser-
    second) is enforced inside this function so shims cannot bypass it.
    """

    blocked = check_safety(prompt)
    if blocked is not None:
        return blocked
    return ParsedToken(payload=parse_exception_token(prompt))
