from src._core.infrastructure.admin.permission_registry import AdminPermissionRegistry


def test_accounts_key_always_present():
    registry = AdminPermissionRegistry()
    assert "accounts" in registry.all_keys()


def test_register_adds_page_key():
    registry = AdminPermissionRegistry()
    registry.register("docs")
    assert "docs" in registry.all_keys()


def test_all_keys_returns_sorted_list():
    registry = AdminPermissionRegistry()
    registry.register("user")
    registry.register("docs")
    registry.register("ai_usage")
    keys = registry.all_keys()
    assert keys == sorted(keys)


def test_is_valid_key_returns_true_for_registered_key():
    registry = AdminPermissionRegistry()
    registry.register("docs")
    assert registry.is_valid_key("docs") is True
    assert registry.is_valid_key("accounts") is True


def test_is_valid_key_returns_false_for_unknown_key():
    registry = AdminPermissionRegistry()
    assert registry.is_valid_key("unknown_page") is False


def test_register_is_idempotent():
    registry = AdminPermissionRegistry()
    registry.register("docs")
    registry.register("docs")
    assert registry.all_keys().count("docs") == 1


def test_accounts_fixed_key_cannot_be_excluded_by_design():
    """accounts is always present — it cannot be deregistered."""
    registry = AdminPermissionRegistry()
    assert "accounts" in registry.all_keys()
    assert registry.is_valid_key("accounts") is True
