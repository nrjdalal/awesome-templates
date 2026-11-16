"""Code-owned registry of operator-editable prompts (#451, ADR 066).

A prompt is editable only if code registered it here, together with the
default text that ships in code. Two things follow:

- The admin page lists exactly these names. An operator cannot create a prompt
  that no agent reads, which is what a typo in a free-form name would do.
- The admin page can show the code default next to the active version. Without
  that, a developer who edits a persona in code sees no change while a stored
  version is active, and nothing on screen says why (ADR066-G5).

Agents register at import time, next to the constant they already pass as
``default`` to ``PromptProviderProtocol.get_active``.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

# Long enough for any persona this repository ships (the longest is ~250
# characters) with room to grow; short enough that a pasted document is
# rejected rather than silently eating the context window.
MAX_PROMPT_LENGTH: Final[int] = 8000

_REGISTRY: dict[str, str] = {}


class PromptRegistrationConflict(ValueError):
    """Two call sites registered one name with different defaults."""


def register_prompt(name: str, default: str) -> None:
    """Register ``name`` as editable, with ``default`` as its code text.

    Idempotent for the same pair — modules can be re-imported under test. A
    second, *different* default for one name is a programming error: the admin
    page could only show one of them, and the agents would disagree.
    """
    if not name or not default:
        raise ValueError("prompt name and default must be non-empty")
    existing = _REGISTRY.get(name)
    if existing is not None and existing != default:
        raise PromptRegistrationConflict(
            f"prompt {name!r} is already registered with a different default"
        )
    _REGISTRY[name] = default


def registered_prompts() -> MappingProxyType[str, str]:
    """Read-only view of ``{name: code default}``."""
    return MappingProxyType(_REGISTRY)


def is_registered(name: str) -> bool:
    return name in _REGISTRY
