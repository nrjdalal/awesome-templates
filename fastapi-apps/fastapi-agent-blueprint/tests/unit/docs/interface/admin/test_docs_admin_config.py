import pytest

pytest.importorskip("nicegui")

from src.docs.interface.admin.configs.docs_admin_config import docs_admin_page


def test_domain_name_matches():
    assert docs_admin_page.domain_name == "docs"


def test_visible_columns_excludes_hidden():
    visible = docs_admin_page.get_visible_columns()
    assert visible
    for col in visible:
        assert not col.hidden


def test_sensitive_fields_masked_when_present():
    sensitive_keywords = {"password", "secret", "api_key", "private_key"}
    for col in docs_admin_page.columns:
        if any(keyword in col.field_name.lower() for keyword in sensitive_keywords):
            assert col.masked, f"{col.field_name} should be masked"


def test_query_extra_service_configured():
    assert docs_admin_page.extra_services_config == {"query": "docs_query_service"}


def test_searchable_fields_configured():
    assert "title" in docs_admin_page.searchable_fields
