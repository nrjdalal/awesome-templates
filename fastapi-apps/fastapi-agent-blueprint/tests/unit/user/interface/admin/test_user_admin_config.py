import pytest

pytest.importorskip("nicegui")

from src.user.interface.admin.configs.user_admin_config import user_admin_page


def test_domain_name_matches():
    assert user_admin_page.domain_name == "user"


def test_visible_columns_excludes_hidden():
    visible = user_admin_page.get_visible_columns()
    field_names = {col.field_name for col in visible}
    assert visible
    assert "role" in field_names
    for col in visible:
        assert not col.hidden


def test_sensitive_fields_masked_when_present():
    sensitive_keywords = {"password", "secret", "api_key", "private_key"}
    for col in user_admin_page.columns:
        if any(keyword in col.field_name.lower() for keyword in sensitive_keywords):
            assert col.masked, f"{col.field_name} should be masked"


def test_password_column_is_masked():
    assert "password" in user_admin_page.get_masked_field_names()


def test_searchable_fields_configured():
    assert {"username", "email"}.issubset(user_admin_page.searchable_fields)
