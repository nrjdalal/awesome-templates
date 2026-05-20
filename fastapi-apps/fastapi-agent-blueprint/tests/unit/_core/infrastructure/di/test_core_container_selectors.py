"""Unit tests for CoreContainer's optional-infra Selector functions (#101, ADR 042).

The selector functions read ``settings`` dynamically at call time, so we can
flip the branch each test picks by monkeypatching the relevant Settings field.
These tests exercise the *decision logic*; the container-level branch resolution
(real client vs ``None``/Stub) is covered by
``tests/integration/test_optional_infra.py``.
"""

from __future__ import annotations

import pytest

from src._core.config import settings
from src._core.infrastructure.di.core_container import (
    _dynamodb_selector,
    _embedding_selector,
    _llm_selector,
    _s3vector_selector,
    _storage_selector,
)


class TestStorageSelector:
    def test_disabled_when_storage_type_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "storage_type", None)
        assert _storage_selector() == "disabled"

    def test_enabled_when_storage_type_s3(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "storage_type", "s3")
        assert _storage_selector() == "enabled"

    def test_enabled_when_storage_type_minio(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "storage_type", "minio")
        assert _storage_selector() == "enabled"


class TestDynamoDBSelector:
    def test_disabled_when_access_key_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "dynamodb_access_key", None)
        assert _dynamodb_selector() == "disabled"

    def test_enabled_when_access_key_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "dynamodb_access_key", "AKIA_TEST")
        assert _dynamodb_selector() == "enabled"


class TestS3VectorSelector:
    def test_disabled_when_access_key_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "s3vectors_access_key", None)
        assert _s3vector_selector() == "disabled"

    def test_enabled_when_access_key_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "s3vectors_access_key", "AKIA_TEST")
        assert _s3vector_selector() == "enabled"


class TestEmbeddingSelector:
    def test_disabled_when_provider_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "embedding_provider", None)
        monkeypatch.setattr(settings, "embedding_model", None)
        assert _embedding_selector() == "disabled"

    def test_disabled_when_only_provider_set(self, monkeypatch: pytest.MonkeyPatch):
        # Both provider AND model required per ``embedding_model_name`` computed property.
        monkeypatch.setattr(settings, "embedding_provider", "openai")
        monkeypatch.setattr(settings, "embedding_model", None)
        assert _embedding_selector() == "disabled"

    def test_enabled_when_provider_and_model_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "embedding_provider", "openai")
        monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
        assert _embedding_selector() == "enabled"


class TestLLMSelector:
    def test_disabled_when_provider_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "llm_provider", None)
        monkeypatch.setattr(settings, "llm_model", None)
        assert _llm_selector() == "disabled"

    def test_disabled_when_only_provider_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "llm_provider", "openai")
        monkeypatch.setattr(settings, "llm_model", None)
        assert _llm_selector() == "disabled"

    def test_enabled_when_provider_and_model_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "llm_provider", "openai")
        monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")
        assert _llm_selector() == "enabled"
