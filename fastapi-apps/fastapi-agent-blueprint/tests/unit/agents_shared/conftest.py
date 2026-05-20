"""Shared fixtures for agents_shared tests (issue #133, AGENT_LOCALE)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_agent_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip ambient ``AGENT_LOCALE`` from every test in this directory.

    Existing hook-behaviour tests (e.g. ``test_completion_gate.py``,
    ``test_governor_phase4.py``) assert English-default byte-equality and
    would fail if a developer's shell exports ``AGENT_LOCALE=ko``. Locale
    tests must explicitly call ``monkeypatch.setenv("AGENT_LOCALE", "ko")``
    inside the test body.
    """
    monkeypatch.delenv("AGENT_LOCALE", raising=False)
