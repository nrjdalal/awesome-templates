"""`VECTOR_STORE_TYPE` boot validation (#328 F8).

It was the only Selector key with no allowed-value tuple and no boot check.
`config.py` declares `KNOWN_ENVS`, `KNOWN_ENGINES`, `KNOWN_BROKER_TYPES`,
`KNOWN_STORAGE_TYPES`, `KNOWN_LLM_PROVIDERS`, `KNOWN_EMBEDDING_PROVIDERS` and
`KNOWN_NOTIFICATION_PROVIDERS`, each with a matching validator — there was no
vector-store tuple.

Two silent misconfigurations followed, both verified before the fix:

- `VECTOR_STORE_TYPE=s3` — the natural typo, since `s3` is the correct spelling
  for `STORAGE_TYPE` in every env example — booted clean in **prod** and raised
  `Selector has no "s3" provider` on the first docs request. A 500 in traffic
  instead of a boot failure.
- `VECTOR_STORE_TYPE=s3vectors` with no credentials booted clean and handed the
  docs domain a `DocumentChunkS3VectorStore(s3vector_client=None, bucket_name='')`,
  so every ingest and query raised `AttributeError` against `None`.

The second is the coupling half: the `s3vectors` branch injects
`core_container.s3vector_client`, whose own Selector is gated on
`settings.s3vectors_access_key` — a *different* field — so the two selectors
could disagree.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

_BASE = {
    "ENV": "local",
    "DATABASE_ENGINE": "sqlite",
    "DATABASE_NAME": ":memory:",
    "DATABASE_USER": "u",
    "DATABASE_PASSWORD": "p",
    "DATABASE_HOST": "h",
    "DATABASE_PORT": "0",
}

_S3VECTORS_CREDENTIALS = {
    "S3VECTORS_REGION": "ap-northeast-2",
    "S3VECTORS_ACCESS_KEY": "key",
    "S3VECTORS_SECRET_KEY": "secret",
    "S3VECTORS_BUCKET_NAME": "bucket",
}


def _settings(**env: str):
    from src._core.config import Settings

    with patch.dict(os.environ, {**_BASE, **env}, clear=True):
        return Settings()


class TestKnownValues:
    def test_unset_is_accepted(self) -> None:
        # inmemory is the documented default; absence must stay valid.
        assert _settings().vector_store_type is None

    @pytest.mark.parametrize("value", ["inmemory", "s3vectors"])
    def test_known_values_are_accepted(self, value: str) -> None:
        assert (
            _settings(
                VECTOR_STORE_TYPE=value, **_S3VECTORS_CREDENTIALS
            ).vector_store_type
            == value
        )

    @pytest.mark.parametrize("value", ["S3Vectors", "  INMEMORY  "])
    def test_case_and_whitespace_are_tolerated(self, value: str) -> None:
        # `_vector_store_selector` lowers and strips, so validation must accept
        # exactly what the selector would.
        _settings(VECTOR_STORE_TYPE=value, **_S3VECTORS_CREDENTIALS)

    def test_the_s3_typo_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="vector_store_type"):
            _settings(VECTOR_STORE_TYPE="s3")

    def test_the_s3_typo_is_rejected_in_prod_too(self) -> None:
        # The case that mattered: it used to boot clean here and 500 later.
        with pytest.raises(ValidationError, match="vector_store_type"):
            _settings(
                ENV="prod",
                VECTOR_STORE_TYPE="s3",
                DATABASE_ENGINE="postgresql",
                DATABASE_NAME="d",
                DATABASE_PORT="5432",
                JWT_SECRET_KEY="x" * 40,
                ADMIN_JWT_SECRET_KEY="y" * 40,
                ADMIN_JWT_AUDIENCE="admin-aud",
                ADMIN_STORAGE_SECRET="z" * 40,
                ADMIN_BOOTSTRAP_ENABLED="false",
                BROKER_TYPE="rabbitmq",
                RABBITMQ_URL="amqp://x",
                ALLOW_ORIGINS='["https://app.example.com"]',
                ALLOWED_HOSTS='["app.example.com"]',
            )


class TestCredentialCoupling:
    def test_s3vectors_without_credentials_is_rejected(self) -> None:
        # Otherwise the docs domain gets a store with s3vector_client=None and
        # fails at request time instead of boot.
        with pytest.raises(
            ValidationError, match="VECTOR_STORE_TYPE=s3vectors requires"
        ):
            _settings(VECTOR_STORE_TYPE="s3vectors")

    def test_s3vectors_with_partial_credentials_is_rejected(self) -> None:
        with pytest.raises(
            ValidationError, match="VECTOR_STORE_TYPE=s3vectors requires"
        ):
            _settings(
                VECTOR_STORE_TYPE="s3vectors",
                S3VECTORS_REGION="ap-northeast-2",
                S3VECTORS_ACCESS_KEY="key",
            )

    def test_s3vectors_with_full_credentials_is_accepted(self) -> None:
        assert (
            _settings(
                VECTOR_STORE_TYPE="s3vectors", **_S3VECTORS_CREDENTIALS
            ).vector_store_type
            == "s3vectors"
        )

    def test_inmemory_does_not_require_credentials(self) -> None:
        assert _settings(VECTOR_STORE_TYPE="inmemory").vector_store_type == "inmemory"
