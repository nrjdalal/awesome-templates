import pytest

pytest.importorskip("nicegui")

from src.ai_usage.interface.admin.configs.ai_usage_admin_config import (
    ai_usage_admin_page,
)


def test_domain_name_matches():
    assert ai_usage_admin_page.domain_name == "ai_usage"


def test_admin_page_is_readonly():
    assert ai_usage_admin_page.readonly is True


def test_visible_columns_excludes_hidden():
    visible = ai_usage_admin_page.get_visible_columns()
    assert visible
    for col in visible:
        assert not col.hidden


def test_sensitive_fields_masked_when_present():
    sensitive_keywords = {"password", "secret", "api_key", "private_key"}
    for col in ai_usage_admin_page.columns:
        if any(keyword in col.field_name.lower() for keyword in sensitive_keywords):
            assert col.masked, f"{col.field_name} should be masked"


def test_searchable_fields_configured():
    assert "call_id" in ai_usage_admin_page.searchable_fields
