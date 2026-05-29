"""Contract test: guardrail exceptions never leak internals to the client
(#197 Phase 3 / #209, codex Round-1 HIGH).

`custom_exception_handler` serializes `exc.details` into the response
`error_details`. The guardrail exceptions force `details=None`, so the matched
injection rule / fabricated-PII token can never reach the client. This test
pins that contract at the handler boundary (the stub answer agent used in e2e
does not exercise the guard path, so this is the authoritative assertion).
"""

from __future__ import annotations

import json

import pytest

from src._core.exceptions.exception_handlers import custom_exception_handler
from src._core.exceptions.llm_exceptions import (
    GuardrailBlocked,
    PromptInjectionDetected,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc,expected_status,expected_code",
    [
        (PromptInjectionDetected(), 400, "PROMPT_INJECTION_DETECTED"),
        (GuardrailBlocked(), 422, "GUARDRAIL_BLOCKED"),
    ],
)
async def test_guardrail_exception_response_has_no_details(
    exc, expected_status: int, expected_code: str
) -> None:
    response = await custom_exception_handler(request=None, exc=exc)  # type: ignore[arg-type]
    assert response.status_code == expected_status

    body = json.loads(response.body)
    assert body["success"] is False
    # Response uses camelCase serialization (errorCode / errorDetails).
    assert body["errorCode"] == expected_code
    # The critical assertion: no internal detail (rule name / PII token) leaks.
    assert body["errorDetails"] is None
    # Message is generic — it does not name the matched rule or any value.
    assert "rule" not in body["message"].lower()
    assert "@" not in body["message"]
