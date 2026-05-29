"""Runtime prompt-injection + PII guardrails (#197 Phase 3 / #209).

Plain, side-effect-free detection functions used by the two PydanticAI agent
adapters (RAG answer + classifier). They are intentionally NOT coupled to
PydanticAI (no Hooks / capabilities API) — the adapters own their call sites,
so an ordinary function called before/after ``agent.run()`` is simpler, fully
unit-testable, and decoupled from the PydanticAI version.

Layered on top of the Phase 1+2 structural baseline (`prompt_boundaries.py`):
Phase 1+2 escapes + boundary-wraps every dynamic field so document content
cannot structurally break out; Phase 3 adds runtime detection of obvious
injection imperatives in the *user* input and fabricated-PII in the *answer*.

Scope is deliberately narrow (codex + Plan-agent review):
- Detection is regex over a curated English-imperative set + a zero-width /
  control-char strip-then-rescan. NO base64/ROT13 decode (infinite-encoding
  recall theater + false-positive minefield) and NO credit-card Luhn.
- ``scan_pii`` returns TYPE-PREFIXED tokens so values cannot collide across
  categories, and both sides of the fabrication diff use identical normalization.
"""

from __future__ import annotations

import re
from typing import Final

# ── Prompt-injection detection ──────────────────────────────────────────────

# Curated, high-signal English imperatives. Each entry is (rule_name, pattern);
# the rule name is for structlog only — it is NEVER returned to the client.
_INJECTION_RULES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "ignore_previous",
        re.compile(
            r"ignore\s+(?:all\s+)?(?:(?:the|your)\s+)?(?:previous|prior)\s+instructions",
            re.I,
        ),
    ),
    (
        "disregard_above",
        re.compile(r"disregard\s+(?:the\s+)?(?:above|prior|previous)", re.I),
    ),
    ("forget_instructions", re.compile(r"forget\s+(?:everything|all|your)\b", re.I)),
    ("you_are_now", re.compile(r"you\s+are\s+now\b", re.I)),
    ("system_marker", re.compile(r"^\s*system\s*:", re.I | re.M)),
    ("new_instructions", re.compile(r"new\s+instructions\s*:", re.I)),
    (
        "reveal_prompt",
        re.compile(
            r"(?:reveal|print|repeat|show)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)",
            re.I,
        ),
    ),
    (
        "override_rules",
        re.compile(r"override\s+(?:your\s+)?(?:rules|guidelines|instructions)", re.I),
    ),
)

# Zero-width + format control chars commonly used to smuggle imperatives past a
# naive scan. We strip these (plus other C0/C1 controls except \t \n \r) and
# rescan, so "ig​nore previous instructions" still trips the rule.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _strip_invisible(text: str) -> str:
    return _INVISIBLE.sub("", text)


def detect_prompt_injection(text: str) -> str | None:
    """Return the matched rule NAME (for logging) or ``None``.

    Scans the raw text and an invisible-char-stripped copy so zero-width
    smuggling cannot bypass the rules. The returned name must only ever reach
    structlog — never the HTTP response (it would tell an attacker which rule
    to evade).
    """
    if not text:
        return None
    stripped = _strip_invisible(text)
    candidates = (text, stripped) if stripped != text else (text,)
    for candidate in candidates:
        for name, pattern in _INJECTION_RULES:
            if pattern.search(candidate):
                return name
    return None


# ── PII scanning (for the fabrication diff) ─────────────────────────────────

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
# Phone: 10-15 digits with common separators. Anchored on boundaries; IPv4-like
# dotted quads are removed first so "192.168.0.1" is not also read as a phone.
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,16}\d)(?!\w)")
_DIGITS = re.compile(r"\D")


def scan_pii(text: str) -> set[str]:
    """Return a set of TYPE-PREFIXED, normalized PII tokens found in ``text``.

    Type prefixes (``email:`` / ``ipv4:`` / ``phone:``) prevent cross-category
    collisions. Normalization is applied so the same value formatted differently
    on the answer vs the source ("555-1234" vs "555 1234") still matches in the
    fabrication diff:
      - email  → lower-cased
      - ipv4   → dotted form as-is
      - phone  → digits only, with a leading ``1`` country code stripped for
        11-digit US numbers so ``555-123-4567`` and ``+1 555 123 4567``
        canonicalize to the same token. This biases toward FEWER false
        positives (a missed fabricated number is less harmful than wrongly
        blocking a legitimately-reformatted one). True international country
        codes are not canonicalized — a documented Phase 3 strictness limit.
    """
    if not text:
        return set()

    tokens: set[str] = set()

    for m in _EMAIL.findall(text):
        tokens.add(f"email:{m.lower()}")

    ipv4_values = set(_IPV4.findall(text))
    for ip in ipv4_values:
        tokens.add(f"ipv4:{ip}")

    # Remove IPv4 matches before phone scanning so dotted quads aren't double-counted.
    phone_search_space = _IPV4.sub(" ", text)
    for m in _PHONE.findall(phone_search_space):
        normalized = _normalize_phone(m)
        if normalized:
            tokens.add(f"phone:{normalized}")

    return tokens


def _normalize_phone(raw: str) -> str:
    """Digits-only phone token, empty if not a plausible 10-15 digit number.

    Strips a single leading ``1`` US country code on 11-digit numbers so the
    same line formatted with/without ``+1`` canonicalizes identically.
    """
    digits = _DIGITS.sub("", raw)
    if not (10 <= len(digits) <= 15):
        return ""
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


# ── Prompt-leak detection (log-only) ────────────────────────────────────────


def find_prompt_leak(answer: str, instructions: str, *, window: int = 100) -> bool:
    """Return True if a contiguous ``window``-char slice of ``instructions``
    appears verbatim in ``answer``.

    Log-only signal (the caller does NOT block on it): the instructions are
    non-secret generic guidance a model may legitimately paraphrase, so a
    short window would false-positive and a long window only catches a verbatim
    dump. Used purely for observability.
    """
    if not answer or not instructions or len(instructions) < window:
        return False
    normalized_answer = " ".join(answer.split())
    normalized_instr = " ".join(instructions.split())
    step = max(window // 2, 1)
    for start in range(0, len(normalized_instr) - window + 1, step):
        if normalized_instr[start : start + window] in normalized_answer:
            return True
    return False
