"""Unit tests for the admin dark-mode toggle resolution (#193).

``ui.dark_mode.toggle()`` raises when the value is None (auto), so the header
toggle resolves the next state via ``_next_dark_value`` instead. These tests
pin that logic without needing a nicegui client context.
"""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")

from src._core.infrastructure.admin.layout import _next_dark_value  # noqa: E402


def test_next_value_from_auto_is_dark():
    # From system/auto (None) the first toggle resolves to an explicit dark.
    assert _next_dark_value(None) is True


def test_next_value_flips_explicit_state():
    assert _next_dark_value(True) is False
    assert _next_dark_value(False) is True


def test_next_value_is_always_concrete_bool():
    for current in (None, True, False):
        assert isinstance(_next_dark_value(current), bool)
