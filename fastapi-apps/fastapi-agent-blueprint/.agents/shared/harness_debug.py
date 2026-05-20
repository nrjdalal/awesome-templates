"""Sanitized debug logging for fail-open harness hooks."""

from __future__ import annotations

import os
import re
import sys

_SENSITIVE_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|access[_-]?key)\b\s*[:=]\s*[^,\s]+"
)


def _sanitize(value: object) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    text = _SENSITIVE_RE.sub(r"\1=<redacted>", text)
    return text[:300]


def debug_log(event: str, exc: BaseException | None = None) -> None:
    """Write a sanitized diagnostic line to stderr when HARNESS_DEBUG=1."""

    if os.environ.get("HARNESS_DEBUG") != "1":
        return
    message = f"[harness-debug] {_sanitize(event)}"
    if exc is not None:
        message = f"{message}: {type(exc).__name__}: {_sanitize(exc)}"
    print(message, file=sys.stderr)
