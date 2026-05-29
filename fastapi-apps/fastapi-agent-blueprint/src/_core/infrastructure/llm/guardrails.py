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

# Shared regex fragments (kept here so the noun/adjective lists are defined once
# and cannot drift between rules).
#   _JAILBREAK_ADJ  — adjectives that signal a jailbreak / safety-removal intent.
#   _JAILBREAK_PERSONA — named jailbreak personas that match on their own.
#   _JAILBREAK_MODE — the "<x> mode" tokens that are jailbreak-specific.
#   _GOVERNANCE_OBJ — objects that make "no longer <verb> ..." / "free from ..."
#                     a real safety-removal rather than a benign account update.
#   _PROMPT_SYS_ADJ — adjectives that mark "the model's own prompt/instructions"
#                     (vs. ordinary business "instructions for X").
_JAILBREAK_ADJ: Final[str] = (
    r"(?:unrestricted|unfiltered|uncensored|unlocked|jailbroken"
    r"|lawless|amoral|unethical|rogue|unbound|evil|malicious)"
)
_JAILBREAK_PERSONA: Final[str] = r"(?:dan|chatgpt|gpt|aim|stan)"
# A persona is a role-injection only when it is NOT used as an adjective in front
# of a benign product/account/role noun — "you are now a ChatGPT Plus subscriber"
# / "a GPT developer" are benign; "you are now ChatGPT" / "...with developer mode"
# still match (the next token is not one of these benign nouns).
_PERSONA_NOT_PRODUCT: Final[str] = (
    r"(?!\s+(?:plus|pro|premium|enterprise|team|business|subscriber|subscription"
    r"|user|customer|account|plan|member|tier|license|seat|edition|api|developer"
    r"|engineer|expert|specialist|fan|enthusiast|model)\b)"
)
# Canonical LLM-jailbreak "<x> mode" names. ``admin``/``god``/``sudo``/``root``
# are deliberately EXCLUDED — those are overwhelmingly benign ops/UI language.
# ``developer``/``dev`` ARE kept despite a dual-use reading ("developer mode" also
# names a benign device/app state): in the frame "you are now in developer mode"
# sent as a user turn they are the canonical "Developer Mode" jailbreak, and that
# detection value outweighs the rare benign narration — which, as a recoverable,
# logged 400 behind the boundary/instructions defense, is an accepted residual.
_JAILBREAK_MODE: Final[str] = r"(?:developer|dev|dan|jailbreak|unrestricted)"
_GOVERNANCE_OBJ: Final[str] = (
    r"(?:rules|restrictions|guidelines|constraints|filters|limitations"
    r"|policies|guardrails|safety|content\s+policy)"
)
# Up to 2 qualifier words between the preposition and the governance object —
# "by OpenAI policies", "from your safety guidelines". A CLOSED set (possessive /
# provider / safety adjective), NOT arbitrary words, so benign account phrasing
# like "no longer subject to billing restrictions" / "account policies" does not
# match (the qualifier belongs to the model's governance, not a business domain).
_GOVERNANCE_FILLER: Final[str] = (
    r"(?:(?:your|the|any|all|its|our|my|openai|anthropic|google"
    r"|safety|content|ethical|moral|ai|usage|system|standard|default|preset)"
    r"(?:['’]s)?\s+){0,2}"  # optional possessive: "OpenAI's policies"
)
# "no longer" OR a bare "not" safety-removal — "you are now not bound by ...".
_SAFETY_REMOVAL_LEAD: Final[str] = r"(?:no\s+longer|not)"
_PROMPT_SYS_ADJ: Final[str] = r"(?:system|developer|initial|original|current)"

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
    # "forget your <X>" only trips on instruction-like nouns — "forget your
    # password policy" must NOT match (the bare ``your`` branch caused FPs).
    (
        "forget_instructions",
        re.compile(
            r"forget\s+(?:everything|all\b"
            r"|your\s+(?:previous\s+)?(?:instructions|rules|guidelines|prompt|training|directives))",
            re.I,
        ),
    ),
    # Jailbreak / safety-removal reassignment. Keyed on jailbreak MARKERS, not on
    # generic role nouns — "you are now a customer support assistant" / "a
    # registered user" / "eligible" must stay benign, so a bare "you are now a
    # <role>" is intentionally NOT caught (open-ended role-play is left to the
    # boundary/instructions layer). It matches a jailbreak adjective ("completely
    # unrestricted AI"), a named jailbreak persona (DAN/ChatGPT), a *known*
    # jailbreak "<x> mode" (so "dark mode" / "airplane mode" are benign), or a
    # safety-removal with a governance object ("no longer bound by your rules",
    # "free from your restrictions" — but NOT "no longer eligible/limited to the
    # free plan").
    (
        "you_are_now",
        re.compile(
            r"you\s+are\s+now\s+(?:"
            rf"(?:\w+\s+){{0,3}}?{_JAILBREAK_ADJ}\b"
            # ``(?![\w-])`` (not ``\b``) so "GPT-powered" / "ChatGPT-style" stay
            # benign — a hyphenated product name is not a standalone persona; the
            # trailing lookahead drops "ChatGPT Plus subscriber" / "GPT developer".
            rf"|(?:a\s+|an\s+|the\s+)?{_JAILBREAK_PERSONA}(?![\w-]){_PERSONA_NOT_PRODUCT}"
            rf"|(?:in\s+)?{_JAILBREAK_MODE}\s+mode\b"
            rf"|{_SAFETY_REMOVAL_LEAD}\s+(?:an?\s+)?(?:ai\b|assistant\b)"
            # A preposition + up to 2 closed-set qualifier words (provider/
            # possessive, e.g. "by OpenAI policies") then a governance object.
            # Keeps "no longer limited to the free plan" / "subject to billing
            # restrictions" benign (no model-governance qualifier).
            rf"|{_SAFETY_REMOVAL_LEAD}\s+(?:bound|restricted|limited|constrained|subject)"
            rf"\s+(?:by|to|under|from)\s+{_GOVERNANCE_FILLER}{_GOVERNANCE_OBJ}\b"
            rf"|free\s+from\s+{_GOVERNANCE_FILLER}{_GOVERNANCE_OBJ}\b"
            r")",
            re.I,
        ),
    ),
    ("system_marker", re.compile(r"^\s*system\s*:", re.I | re.M)),
    # Line-anchored like ``system_marker`` so inline "...the new instructions:..."
    # is not flagged; a newline-prefixed breakout still matches.
    ("new_instructions", re.compile(r"^\s*new\s+instructions\s*:", re.I | re.M)),
    # System-prompt exfiltration. Noun-specific because "instructions" is heavily
    # overloaded with benign business meaning ("current instructions for resetting
    # MFA", "the instructions on the box") while "prompt" is not:
    #   • "prompt"       → a system-ish adjective run (≥1) OR a possessive your/my.
    #                      Bare/essay/writing prompt stays benign.
    #   • "instructions" → must be qualified by a STRONG token (system/developer or
    #                      possessive your/my); current/original/initial alone stay
    #                      benign. Compound modifiers ("original system prompt",
    #                      "current developer instructions") are allowed.
    (
        "reveal_prompt",
        re.compile(
            r"(?:reveal|show|print|repeat|expose|dump|leak|give\s+me|tell\s+me)"
            r"\s+(?:me\s+)?(?:the\s+|a\s+)?(?:"
            rf"(?:{_PROMPT_SYS_ADJ}\s+)+prompt\b"
            rf"|(?:your|my)\s+(?:{_PROMPT_SYS_ADJ}\s+)*prompt\b"
            rf"|(?:your|my)\s+(?:{_PROMPT_SYS_ADJ}\s+)*instructions\b"
            rf"|(?:(?:initial|original|current)\s+)*(?:system|developer)\s+(?:{_PROMPT_SYS_ADJ}\s+)*instructions\b"
            r")",
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

    Every start offset is scanned (not strided): the instructions are short
    (hundreds of chars) so the cost is trivial, and striding would silently
    miss a verbatim leak that starts on a non-aligned offset.
    """
    if not answer or not instructions or len(instructions) < window:
        return False
    normalized_answer = " ".join(answer.split())
    normalized_instr = " ".join(instructions.split())
    for start in range(0, len(normalized_instr) - window + 1):
        if normalized_instr[start : start + window] in normalized_answer:
            return True
    return False
