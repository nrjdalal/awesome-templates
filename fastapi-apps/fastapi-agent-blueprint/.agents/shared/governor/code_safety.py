"""Code content safety rules for PreToolUse hooks (Claude-side).

``check_code_safety`` is the single source of truth for the four security
pattern categories that were previously inline in
``.claude/hooks/pre_tool_security.py::check_security()`` (Phase 5 / PR-A.4 cleanup).

Public API:
  ``check_code_safety(path, content) -> list[str]`` — returns a (possibly
    empty) list of human-readable violation messages.

Categories:
  1. SQL injection (f-string SQL, .format() SQL, text-with-f-string, execute-with-f-string)
  2. Hardcoded secrets (sensitive keyword = quoted literal, excluding test files,
     Pydantic Field, env-var access patterns)
  3. Domain -> Infrastructure import violation
  4. Sensitive data in log/print calls

Boundary: content-level pattern detection only. Tool-input routing
(which tool called, path extraction, ``_extract_bash_write`` for Bash
writes) remains in the Claude hook shim because it is tool-specific.
"""

from __future__ import annotations

import posixpath
import re

# Quoted-value fragment: matches triple-quoted or single-quoted literals >= 3 chars.
_QUOTED_VALUE_RE = (
    r"(?:[bruf]*)(?:"
    r'"{3}[\s\S]{3,}?"{3}'  # """..."""
    r"|\x27{3}[\s\S]{3,}?\x27{3}"  # '''...'''
    r'|["\x27][^"\x27\s]{3,}["\x27]'  # "..." or '...'
    r")"
)

_SENSITIVE_KEYWORDS = [
    r"(?:password|passwd|pwd)",
    r"(?:secret|secret_key)",
    r"(?:api_key|apikey)",
    r"(?:private_key)",
    r"(?:auth_token)",
    r"(?:encryption_key)",
    r"(?:credential)",
    r"(?:access_token)",
]

# Pre-compile the env-var / Pydantic allow-list pattern (used inside secret check).
_SECRET_ALLOW_LIST = re.compile(
    r"(Field\s*\(|os\.environ|settings\.|getenv|validation_alias|\.env)"
)

# Pre-compile the sensitive-log pattern.
_LOG_PATTERN = re.compile(
    r"(?:logger\.|logging\.|print\s*\().*(?:password|secret|token|api_key|private_key)",
    re.IGNORECASE,
)

# SQL-injection patterns (pre-compiled at module load).
# Pattern names encode which SQLAlchemy anti-pattern each guards against.
_FSTRING_SQL_RE = re.compile(
    r'f["\x27].*\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b', re.IGNORECASE
)
_FORMAT_SQL_RE = re.compile(
    r"\.format\s*\(.*\).*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE
)
# Matches SQLAlchemy text() called with an f-string argument.
# Written as a split string to avoid triggering this file's own hook shim.
_TEXT_FSTRING_RE = re.compile(r"text\s*\(\s*f" + r'["\x27]')
# Matches execute() called with an f-string or .format() argument.
_EXECUTE_FSTRING_RE = re.compile(r"\.execute\s*\(\s*f" + r'["\x27]')
_EXECUTE_FORMAT_RE = re.compile(r'\.execute\s*\(["\x27].*\.format\s*\(', re.IGNORECASE)
_DOMAIN_INFRA_RE = re.compile(r"from\s+src\..*\.infrastructure")


def _path_segments(path: str) -> list[str]:
    """Return the canonical POSIX path segments of *path*, with ``.``/``..`` collapsed.

    ``posixpath.normpath`` resolves ``.`` and ``..`` lexically without touching
    the filesystem (safe for a not-yet-written target), so a traversal such as
    ``./tests/../src/config.py`` resolves to its real target (``src/config.py``)
    *before* any segment is inspected. Callers then match on whole path
    segments rather than substrings, which stops a bare ``/tests/`` or
    ``/domain/`` fragment from being spoofed inside another component.

    Separators are POSIX-only by design: the hooks run on macOS/Linux and a
    backslash is a *valid filename character* there, so folding ``\\`` to ``/``
    would let ``src\\tests\\config.py`` (a single production filename) masquerade
    as a ``tests/`` path and skip the secret check. Backslashes are therefore
    left intact.

    Residual limits (not resolved here — lexical, not filesystem, analysis):
    symlinked directories and case-insensitive aliases (e.g. ``Domain`` on a
    case-preserving APFS/HFS+ volume) can still make a real target differ from
    its textual segments.
    """
    return posixpath.normpath(path).split("/")


def check_code_safety(path: str, content: str) -> list[str]:
    """Check *content* (to be written to *path*) for security violations.

    Returns a list of human-readable messages, one per violation found.
    An empty list means all checks passed.
    """
    errors: list[str] = []

    # 1a. SQL injection: f-string containing SQL keyword
    if _FSTRING_SQL_RE.search(content):
        errors.append(
            "SQL injection risk: f-string SQL detected. "
            "Use parameterized queries (SQLAlchemy ORM or text(:param))"
        )

    # 1b. SQL injection: .format() followed by SQL keyword
    if _FORMAT_SQL_RE.search(content):
        errors.append(
            "SQL injection risk: .format() SQL detected. Use parameterized queries"
        )

    # 1c. SQL injection: SQLAlchemy text() receiving an f-string argument
    if _TEXT_FSTRING_RE.search(content):
        errors.append(
            "SQL injection risk: text() with f-string argument detected. "
            "Use text(:param) + bindparams"
        )

    # 1d. SQL injection: execute() receiving an f-string or .format() argument
    if _EXECUTE_FSTRING_RE.search(content):
        errors.append(
            "SQL injection risk: execute() with f-string argument detected. "
            "Use parameterized queries"
        )
    if _EXECUTE_FORMAT_RE.search(content):
        errors.append(
            'SQL injection risk: execute("...".format()) detected. Use parameterized queries'
        )

    # Canonical, traversal-resolved segments — reused by the test-file and
    # domain-layer checks below so neither can be spoofed by a crafted path
    # (e.g. "./tests/../src/config.py").
    segments = _path_segments(path)

    # 2. Hardcoded secrets (skip test files; skip env-var / Pydantic allow-list patterns)
    is_test_file = "tests" in segments or segments[-1].endswith("_test.py")
    if not is_test_file:
        secret_patterns = [
            kw + r"\s*=\s*" + _QUOTED_VALUE_RE for kw in _SENSITIVE_KEYWORDS
        ]
        for pat in secret_patterns:
            if re.search(pat, content, re.IGNORECASE):
                if not _SECRET_ALLOW_LIST.search(content):
                    errors.append(
                        "Hardcoded secret detected. "
                        "Use environment variables (Settings) or a secret manager"
                    )
                    break

    # 3. Domain -> Infrastructure import violation
    if "domain" in segments:
        if _DOMAIN_INFRA_RE.search(content):
            errors.append(
                "Architecture violation: Domain layer must not import Infrastructure. "
                "Use Protocol (DIP)"
            )

    # 4. Sensitive data in log / print
    if _LOG_PATTERN.search(content):
        errors.append(
            "Sensitive data exposure risk in logs: "
            "password/secret/token found in log output. Masking required"
        )

    return errors
