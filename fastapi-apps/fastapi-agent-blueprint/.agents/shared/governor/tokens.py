"""Phase 2 exception-token vocabulary + canonical parser.

Single source of truth for the token regex, vocabulary set, and the
``parse_exception_token`` function that ``.{claude,codex}/hooks/
user-prompt-submit.*`` previously duplicated.

Behaviour invariance contract (HC-5.1): identical input must produce
identical output to the pre-Phase-5 implementations. The body therefore
mirrors the original implementations verbatim — including the NFKC
normalisation, ASCII-lowercasing, and Korean pass-through.

Decision payload (IC-3, shared with Claude / Codex hooks):
    {"matched": bool, "token": str | None, "rationale_required": bool}
"""

from __future__ import annotations

import re
import unicodedata

TOKEN_REGEX: re.Pattern[str] = re.compile(
    r"^\s*\[(trivial|hotfix|exploration|자명|긴급|탐색)\](?:\s|$)",
    re.IGNORECASE,
)

EXPLORATION_TOKENS: frozenset[str] = frozenset({"exploration", "탐색"})


def parse_exception_token(prompt: str) -> dict:
    """Return canonical decision payload per IC-3.

    Always returns the same shape regardless of input. Token name is
    lowercased for English variants; Korean tokens pass through unchanged
    after NFKC normalisation.
    """

    if not prompt:
        return {"matched": False, "token": None, "rationale_required": False}

    normalised = unicodedata.normalize("NFKC", prompt)
    match = TOKEN_REGEX.match(normalised)
    if not match:
        return {"matched": False, "token": None, "rationale_required": False}

    token = match.group(1)
    if token.isascii():
        token = token.lower()
    return {"matched": True, "token": token, "rationale_required": True}
