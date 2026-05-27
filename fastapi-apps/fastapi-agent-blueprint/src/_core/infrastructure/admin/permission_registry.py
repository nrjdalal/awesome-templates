from __future__ import annotations

_FIXED_KEYS: frozenset[str] = frozenset({"accounts"})


class AdminPermissionRegistry:
    """Registry of admin page permission keys.

    Built at bootstrap time from registered page_configs (domain page keys) plus
    the fixed 'accounts' key (the account-management gate).

    Keys added here are the canonical source for:
    - The checkbox list shown on /admin/accounts (edit-perms form)
    - The all-permissions set granted to the first admin on setup
    - Gate validation in require_auth(page_key=...)
    """

    def __init__(self) -> None:
        self._keys: set[str] = set(_FIXED_KEYS)

    def register(self, page_key: str) -> None:
        self._keys.add(page_key)

    def all_keys(self) -> list[str]:
        return sorted(self._keys)

    def is_valid_key(self, key: str) -> bool:
        return key in self._keys
