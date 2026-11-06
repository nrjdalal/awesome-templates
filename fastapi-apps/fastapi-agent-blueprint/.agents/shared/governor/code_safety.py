"""Retired runtime content checks; compatibility for existing hook adapters.

ADR 061 moves sensitive logging to a deterministic commit hook. Gitleaks,
Ruff/security review and architecture import gates remain separate authorities;
this no-op does not claim equivalent SQL-injection or secret detection.
Antigravity imports this symbol alongside shell safety, so removing the module
would disable its active destructive-command guard through fail-open handling.
"""

from __future__ import annotations


def check_code_safety(path: str, content: str) -> list[str]:
    """No runtime content heuristics; commit gates own the retained checks."""
    return []
