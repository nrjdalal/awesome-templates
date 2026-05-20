import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

_REQUIRED_VARS = {
    "ADMIN_STORAGE_SECRET": "change-me-in-production",
    "DATABASE_ENGINE": "postgresql",
    "DATABASE_USER": "postgres",
    "DATABASE_PASSWORD": "postgres",
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5432",
    "DATABASE_NAME": "postgres",
}


def _make_safe_env(env_name: str = "prod") -> dict[str, str]:
    return {
        **_REQUIRED_VARS,
        "ENV": env_name,
        "ADMIN_STORAGE_SECRET": "a-real-secret-key-here",
        "DATABASE_USER": "app_user",
        "DATABASE_PASSWORD": "db-s3cure-p@ss",
        "DATABASE_HOST": "db.internal.example.com",
        "DATABASE_NAME": "myapp_db",
        "JWT_SECRET_KEY": "a-real-jwt-secret-key-with-enough-length",
        "TASK_NAME_PREFIX": "myapp",
        "BROKER_TYPE": "sqs",
        "AWS_SQS_ACCESS_KEY": "test-key",
        "AWS_SQS_SECRET_KEY": "test-secret",
        "AWS_SQS_URL": "https://sqs.ap-northeast-2.amazonaws.com/123/test",
    }


def _create_settings():
    from src._core.config import Settings

    return Settings()


class TestLocalEnv:
    def test_local_env_accepts_required_fields(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.env == "local"
            assert s.database_engine == "postgresql"
            assert s.database_host == "localhost"

    def test_dev_env_accepts_required_fields(self):
        env = {"ENV": "dev", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.env == "dev"

    def test_test_env_is_rejected(self):
        env = {"ENV": "test", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown environment"):
                _create_settings()


class TestStrictEnvRejectsUnsafeDefaults:
    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    @pytest.mark.parametrize(
        "field_name,unsafe_value",
        [
            ("ADMIN_STORAGE_SECRET", "change-me-in-production"),
            ("DATABASE_PASSWORD", "postgres"),
            ("DATABASE_HOST", "localhost"),
            ("JWT_SECRET_KEY", "change-me-in-production"),
        ],
    )
    def test_strict_env_rejects_each_unsafe_default(
        self, env_name, field_name, unsafe_value
    ):
        safe_env = _make_safe_env(env_name)
        safe_env[field_name] = unsafe_value
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match=field_name.lower()):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_passes_with_safe_values(self, env_name):
        with patch.dict(os.environ, _make_safe_env(env_name), clear=True):
            s = _create_settings()
            assert s.env == env_name

    def test_all_errors_reported_at_once(self):
        env = {"ENV": "prod", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                _create_settings()
            error_message = str(exc_info.value)
            assert "5 error(s)" in error_message

    def test_admin_bootstrap_requires_password_when_enabled(self):
        env = {"ENV": "local", "ADMIN_BOOTSTRAP_ENABLED": "true", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="ADMIN_BOOTSTRAP_PASSWORD"):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_rejects_unsafe_admin_bootstrap_password(self, env_name):
        safe_env = _make_safe_env(env_name)
        safe_env["ADMIN_BOOTSTRAP_ENABLED"] = "true"
        safe_env["ADMIN_BOOTSTRAP_PASSWORD"] = "admin"
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match="admin_bootstrap_password"):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_requires_explicit_jwt_secret(self, env_name):
        safe_env = _make_safe_env(env_name)
        safe_env.pop("JWT_SECRET_KEY")
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    @pytest.mark.parametrize("jwt_secret", ["short-secret", "jwt-secret"])
    def test_strict_env_rejects_weak_jwt_secret(self, env_name, jwt_secret):
        safe_env = _make_safe_env(env_name)
        safe_env["JWT_SECRET_KEY"] = jwt_secret
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match="jwt_secret_key"):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_rejects_unsupported_jwt_algorithm(self, env_name):
        safe_env = _make_safe_env(env_name)
        safe_env["JWT_ALGORITHM"] = "RS256"
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match="HS256"):
                _create_settings()

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_rejects_ai_usage_public_api(self, env_name):
        safe_env = _make_safe_env(env_name)
        safe_env["AI_USAGE_PUBLIC_API_ENABLED"] = "true"
        with patch.dict(os.environ, safe_env, clear=True):
            with pytest.raises(ValidationError, match="AI_USAGE_PUBLIC_API_ENABLED"):
                _create_settings()


class TestUnknownEnv:
    def test_unknown_env_rejected(self):
        env = {"ENV": "production", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown environment"):
                _create_settings()

    @pytest.mark.parametrize("env_val", ["PROD", "Prod", "prod"])
    def test_env_case_insensitive(self, env_val):
        safe = _make_safe_env()
        safe["ENV"] = env_val
        with patch.dict(os.environ, safe, clear=True):
            s = _create_settings()
            assert s.env == env_val


class TestPartialConfigGroups:
    def test_partial_s3_rejected(self):
        env = {"ENV": "local", "S3_ACCESS_KEY": "foo", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"S3.*Partial configuration"):
                _create_settings()

    def test_complete_s3_accepted(self):
        env = {
            "ENV": "local",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
            "S3_REGION": "us-east-1",
            "S3_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.s3_access_key == "key"

    def test_partial_minio_rejected(self):
        env = {"ENV": "local", "MINIO_HOST": "localhost", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"MinIO.*Partial configuration"):
                _create_settings()

    def test_complete_minio_accepted(self):
        env = {
            "ENV": "local",
            "MINIO_HOST": "localhost",
            "MINIO_PORT": "9000",
            "MINIO_ACCESS_KEY": "key",
            "MINIO_SECRET_KEY": "secret",
            "MINIO_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.minio_host == "localhost"

    def test_no_s3_no_minio_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.s3_access_key is None
            assert s.minio_host is None

    def test_partial_dynamodb_rejected(self):
        env = {"ENV": "local", "DYNAMODB_REGION": "ap-northeast-2", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValidationError, match=r"DynamoDB.*Partial configuration"
            ):
                _create_settings()

    def test_complete_dynamodb_accepted(self):
        env = {
            "ENV": "local",
            "DYNAMODB_REGION": "ap-northeast-2",
            "DYNAMODB_ACCESS_KEY": "key",
            "DYNAMODB_SECRET_KEY": "secret",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.dynamodb_region == "ap-northeast-2"

    def test_no_dynamodb_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.dynamodb_region is None

    def test_partial_s3vectors_rejected(self):
        env = {"ENV": "local", "S3VECTORS_REGION": "us-east-2", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValidationError, match=r"S3Vectors.*Partial configuration"
            ):
                _create_settings()

    def test_complete_s3vectors_accepted(self):
        env = {
            "ENV": "local",
            "S3VECTORS_REGION": "us-east-2",
            "S3VECTORS_ACCESS_KEY": "key",
            "S3VECTORS_SECRET_KEY": "secret",
            "S3VECTORS_BUCKET_NAME": "my-vectors",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.s3vectors_region == "us-east-2"

    def test_no_s3vectors_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.s3vectors_region is None


class TestStorageTypeConfig:
    def test_no_storage_type_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_type is None

    def test_unknown_storage_type_rejected(self):
        env = {"ENV": "local", "STORAGE_TYPE": "gcs", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown storage type"):
                _create_settings()

    def test_s3_without_config_rejected(self):
        env = {"ENV": "local", "STORAGE_TYPE": "s3", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValidationError, match=r"Storage.*STORAGE_TYPE=s3.*missing"
            ):
                _create_settings()

    def test_s3_with_complete_config_accepted(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "s3",
            "S3_ACCESS_KEY": "s3-key",
            "S3_SECRET_KEY": "s3-secret",
            "S3_REGION": "ap-northeast-2",
            "S3_BUCKET_NAME": "my-bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_type == "s3"
            assert s.storage_access_key == "s3-key"
            assert s.storage_secret_key == "s3-secret"
            assert s.storage_bucket_name == "my-bucket"

    def test_minio_without_config_rejected(self):
        env = {"ENV": "local", "STORAGE_TYPE": "minio", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValidationError, match=r"Storage.*STORAGE_TYPE=minio.*missing"
            ):
                _create_settings()

    def test_minio_with_complete_config_accepted(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "minio",
            "MINIO_HOST": "localhost",
            "MINIO_PORT": "9000",
            "MINIO_ACCESS_KEY": "minio-key",
            "MINIO_SECRET_KEY": "minio-secret",
            "MINIO_BUCKET_NAME": "minio-bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_type == "minio"
            assert s.storage_access_key == "minio-key"
            assert s.storage_secret_key == "minio-secret"
            assert s.storage_bucket_name == "minio-bucket"

    def test_minio_endpoint_url_resolved(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "minio",
            "MINIO_HOST": "localhost",
            "MINIO_PORT": "9000",
            "MINIO_ACCESS_KEY": "key",
            "MINIO_SECRET_KEY": "secret",
            "MINIO_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_endpoint_url == "localhost:9000"

    def test_s3_endpoint_url_is_none(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "s3",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
            "S3_REGION": "us-east-1",
            "S3_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_endpoint_url is None

    def test_minio_region_is_us_east_1(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "minio",
            "MINIO_HOST": "localhost",
            "MINIO_PORT": "9000",
            "MINIO_ACCESS_KEY": "key",
            "MINIO_SECRET_KEY": "secret",
            "MINIO_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_region == "us-east-1"

    def test_s3_region_resolved(self):
        env = {
            "ENV": "local",
            "STORAGE_TYPE": "s3",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
            "S3_REGION": "ap-northeast-2",
            "S3_BUCKET_NAME": "bucket",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.storage_region == "ap-northeast-2"


class TestBrokerConfig:
    def test_local_no_broker_type_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.broker_type is None

    @pytest.mark.parametrize("env_name", ["prod", "stg"])
    def test_strict_env_requires_broker_type(self, env_name):
        safe = _make_safe_env(env_name)
        del safe["BROKER_TYPE"]
        with patch.dict(os.environ, safe, clear=True):
            with pytest.raises(ValidationError, match="broker_type.*required"):
                _create_settings()

    def test_unknown_broker_type_rejected(self):
        env = {"ENV": "local", "BROKER_TYPE": "kafka", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown broker type"):
                _create_settings()

    def test_sqs_partial_config_rejected(self):
        env = {
            "ENV": "local",
            "BROKER_TYPE": "sqs",
            "AWS_SQS_ACCESS_KEY": "key",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"SQS.*missing"):
                _create_settings()

    def test_sqs_complete_config_accepted(self):
        env = {
            "ENV": "local",
            "BROKER_TYPE": "sqs",
            "AWS_SQS_ACCESS_KEY": "key",
            "AWS_SQS_SECRET_KEY": "secret",
            "AWS_SQS_URL": "https://sqs.ap-northeast-2.amazonaws.com/123/test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.broker_type == "sqs"

    def test_rabbitmq_without_url_rejected(self):
        env = {"ENV": "local", "BROKER_TYPE": "rabbitmq", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"RabbitMQ.*missing"):
                _create_settings()

    def test_rabbitmq_with_url_accepted(self):
        env = {
            "ENV": "local",
            "BROKER_TYPE": "rabbitmq",
            "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.broker_type == "rabbitmq"

    def test_inmemory_accepted(self):
        env = {"ENV": "local", "BROKER_TYPE": "inmemory", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.broker_type == "inmemory"


class TestEmbeddingConfig:
    def test_no_embedding_provider_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_provider is None

    def test_unknown_embedding_provider_rejected(self):
        env = {"ENV": "local", "EMBEDDING_PROVIDER": "cohere", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown embedding provider"):
                _create_settings()

    def test_openai_without_api_key_rejected(self):
        env = {"ENV": "local", "EMBEDDING_PROVIDER": "openai", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"Embedding/OpenAI.*missing"):
                _create_settings()

    def test_openai_with_api_key_accepted(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_OPENAI_API_KEY": "sk-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_provider == "openai"
            assert s.embedding_openai_api_key == "sk-test"

    def test_embedding_dimension_property_openai_default(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_OPENAI_API_KEY": "sk-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 1536

    def test_embedding_dimension_property_openai_large_model(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_OPENAI_API_KEY": "sk-test",
            "EMBEDDING_MODEL": "text-embedding-3-large",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 3072

    def test_embedding_dimension_property_bedrock_default(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "bedrock",
            "EMBEDDING_BEDROCK_ACCESS_KEY": "key",
            "EMBEDDING_BEDROCK_SECRET_KEY": "secret",
            "EMBEDDING_BEDROCK_REGION": "us-east-1",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 1024

    def test_bedrock_partial_config_rejected(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "bedrock",
            "EMBEDDING_BEDROCK_ACCESS_KEY": "key",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"Embedding/Bedrock.*missing"):
                _create_settings()

    def test_bedrock_complete_config_accepted(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "bedrock",
            "EMBEDDING_BEDROCK_ACCESS_KEY": "key",
            "EMBEDDING_BEDROCK_SECRET_KEY": "secret",
            "EMBEDDING_BEDROCK_REGION": "us-east-1",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_provider == "bedrock"
            assert s.embedding_bedrock_region == "us-east-1"

    def test_embedding_model_name_property(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "EMBEDDING_OPENAI_API_KEY": "sk-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_model_name == "openai:text-embedding-3-small"

    def test_embedding_model_name_none_without_provider(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_model_name is None

    def test_embedding_dimension_google(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "google",
            "EMBEDDING_MODEL": "gemini-embedding-001",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 768

    def test_embedding_dimension_ollama(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "ollama",
            "EMBEDDING_MODEL": "all-MiniLM-L6-v2",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 384

    def test_embedding_dimension_sentence_transformers(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "sentence-transformers",
            "EMBEDDING_MODEL": "all-mpnet-base-v2",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_dimension == 768

    def test_google_provider_accepted(self):
        env = {
            "ENV": "local",
            "EMBEDDING_PROVIDER": "google",
            "EMBEDDING_MODEL": "gemini-embedding-001",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.embedding_provider == "google"


class TestLLMConfig:
    def test_no_llm_provider_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.llm_provider is None
            assert s.llm_model_name is None

    def test_unknown_llm_provider_rejected(self):
        env = {"ENV": "local", "LLM_PROVIDER": "gemini", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match="Unknown LLM provider"):
                _create_settings()

    def test_openai_without_api_key_rejected(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"LLM.*llm_api_key missing"):
                _create_settings()

    def test_openai_with_api_key_accepted(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o",
            "LLM_API_KEY": "sk-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.llm_provider == "openai"
            assert s.llm_model == "gpt-4o"
            assert s.llm_model_name == "openai:gpt-4o"

    def test_anthropic_without_api_key_rejected(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "claude-sonnet-4-20250514",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"LLM.*llm_api_key missing"):
                _create_settings()

    def test_anthropic_with_api_key_accepted(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "claude-sonnet-4-20250514",
            "LLM_API_KEY": "sk-ant-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.llm_model_name == "anthropic:claude-sonnet-4-20250514"

    def test_bedrock_partial_config_rejected(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "bedrock",
            "LLM_MODEL": "anthropic.claude-v2",
            "LLM_BEDROCK_ACCESS_KEY": "key",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError, match=r"LLM/Bedrock.*missing"):
                _create_settings()

    def test_bedrock_complete_config_accepted(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "bedrock",
            "LLM_MODEL": "anthropic.claude-v2",
            "LLM_BEDROCK_ACCESS_KEY": "key",
            "LLM_BEDROCK_SECRET_KEY": "secret",
            "LLM_BEDROCK_REGION": "us-east-1",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.llm_model_name == "bedrock:anthropic.claude-v2"

    def test_llm_model_name_none_without_model(self):
        env = {
            "ENV": "local",
            "LLM_PROVIDER": "openai",
            "LLM_API_KEY": "sk-test",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.llm_model_name is None


class TestWarnDefaults:
    def test_task_name_prefix_warns_in_strict_env(self):
        safe = _make_safe_env("prod")
        safe["TASK_NAME_PREFIX"] = "my-project"
        with patch.dict(os.environ, safe, clear=True):
            with pytest.warns(UserWarning, match="task_name_prefix"):
                _create_settings()

    def test_task_name_prefix_no_warn_in_local(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("error")
                _create_settings()


class TestOtelConfig:
    def test_otel_disabled_by_default_accepted(self):
        env = {"ENV": "local", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.otel_enabled is False
            assert s.otel_exporter_otlp_endpoint is None

    def test_otel_enabled_without_endpoint_rejected(self):
        env = {"ENV": "local", "OTEL_ENABLED": "true", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValidationError,
                match=r"OTEL.*otel_exporter_otlp_endpoint missing",
            ):
                _create_settings()

    def test_otel_enabled_with_endpoint_accepted(self):
        env = {
            "ENV": "local",
            "OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            **_REQUIRED_VARS,
        }
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.otel_enabled is True
            assert s.otel_exporter_otlp_endpoint == "http://localhost:4317"


class TestDocsUrlGating:
    """`docs_url` / `redoc_url` / `openapi_url` are exposed only in dev envs.

    Frontend handoff and /openapi-download.json depend on the same gate, so a
    regression here would silently expose specs in prod. See `docs_router` and
    `frontend-handoff.md`.
    """

    def test_docs_urls_exposed_in_dev(self):
        env = {"ENV": "dev", **_REQUIRED_VARS}
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.is_dev is True
            assert s.docs_url == "/docs-swagger"
            assert s.redoc_url == "/docs-redoc"
            assert s.openapi_url == "/openapi.json"

    def test_docs_urls_disabled_in_prod(self):
        env = _make_safe_env("prod")
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.is_dev is False
            assert s.docs_url is None
            assert s.redoc_url is None
            assert s.openapi_url is None

    def test_docs_urls_disabled_in_stg(self):
        env = _make_safe_env("stg")
        with patch.dict(os.environ, env, clear=True):
            s = _create_settings()
            assert s.is_dev is False
            assert s.docs_url is None
            assert s.openapi_url is None
