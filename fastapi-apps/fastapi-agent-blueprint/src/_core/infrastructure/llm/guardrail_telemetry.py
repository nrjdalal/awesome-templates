"""Standardized structlog telemetry for runtime LLM guardrails (#197 Phase 5).

A single ``guardrail_triggered`` event shape across the RAG and classifier
adapters so observability queries (and the ``ai_usage.guardrail_triggered``
ledger column) have a consistent surface.

Field contract — emitted on the ``guardrail_triggered`` event:
- ``agent``   : which call site fired it (``docs_answer`` / ``classification``)
- ``action``  : ``block`` (request was rejected) or ``log`` (observed only)
- ``stage``   : ``input`` (prompt-injection) or ``output`` (PII / prompt-leak)
- ``rule``    : the matched rule name (the issue's "pattern"; kept as ``rule``
                so existing assertions in ``test_answer_agent_guardrails.py``
                stay green)
- ``count`` / ``types`` : optional, output PII-fabrication aggregates only

``request_id`` / ``user_id`` are NOT passed here — they are injected by
``structlog.contextvars.merge_contextvars`` from the per-request binding done
at the HTTP boundary (see ``request_log_middleware`` / the auth dependency),
so every event in the request automatically carries them.

CRITICAL: never pass raw user input, PII values, or model output here — only
the rule name, counts, and PII *type* tokens (``email`` / ``ipv4`` / ``phone``).
"""

from __future__ import annotations

from typing import Any, Literal

import structlog

GuardrailAction = Literal["block", "log"]
GuardrailStage = Literal["input", "output"]


def log_guardrail_event(
    logger: structlog.stdlib.BoundLogger,
    *,
    agent: str,
    stage: GuardrailStage,
    rule: str,
    action: GuardrailAction,
    count: int | None = None,
    types: list[str] | None = None,
) -> None:
    """Emit a standardized ``guardrail_triggered`` warning record."""
    fields: dict[str, Any] = {
        "agent": agent,
        "stage": stage,
        "rule": rule,
        "action": action,
    }
    if count is not None:
        fields["count"] = count
    if types is not None:
        fields["types"] = types
    logger.warning("guardrail_triggered", **fields)
