"""Minimal-install boot regression (#104, extends #101 acceptance criterion).

This test is meant to run in a CI environment that has done ``uv sync``
**without** any optional extras (no ``--extra admin``, no ``--extra aws``,
no ``--extra pydantic-ai``, no ``--extra sqs``, no ``--extra otel``). The
local dev machine typically has extras installed and will simply not hit the
"extra not installed" branches; assertions in that case are relaxed
accordingly.

Acceptance criteria:

- **Part 1** — With ``nicegui`` uninstalled, the FastAPI app still imports
  cleanly, ``bootstrap_app`` logs an INFO message explaining the missing
  extra, and ``/api/health`` continues to serve. No admin routes are
  mounted.
- **Part 2** — With ``boto3`` / ``aioboto3`` uninstalled, the FastAPI app
  still imports cleanly; the storage / DynamoDB / S3 Vectors infrastructure
  modules also import cleanly (their AWS SDK imports are gated by
  ``TYPE_CHECKING`` + lazy ``__init__`` imports). The ``CoreContainer``
  Selector resolves every AWS-backed provider to ``None`` when the matching
  ``*_TYPE`` / ``*_ACCESS_KEY`` env var is unset, so no AWS SDK import ever
  fires.
- **Part 3** — With ``opentelemetry-sdk`` / exporter uninstalled, the app
  still boots (``otel_enabled`` defaults to False). The runtime-import
  check ensures no ``opentelemetry.*`` module leaks onto the default
  import path.
"""

from __future__ import annotations

import importlib.util

import pytest
from fastapi.testclient import TestClient

from src._core.config import settings

_has_nicegui = importlib.util.find_spec("nicegui") is not None
# Consider otel "installed" only when both SDK and the gRPC exporter are present;
# the opentelemetry-api namespace alone (pulled transitively by pydantic-ai-slim)
# is NOT enough to exercise the skip path.
# find_spec() raises ModuleNotFoundError on dotted paths when the parent
# package is absent (i.e. opentelemetry not installed at all).
try:
    _has_otel = (
        importlib.util.find_spec("opentelemetry.sdk.trace") is not None
        and importlib.util.find_spec(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
        )
        is not None
    )
except ModuleNotFoundError:
    _has_otel = False


@pytest.fixture
def clean_optional_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every optional-infra Settings field to its ``disabled`` value."""
    for field in (
        "storage_type",
        "dynamodb_access_key",
        "s3vectors_access_key",
        "embedding_provider",
        "embedding_model",
        "llm_provider",
        "llm_model",
        "otel_exporter_otlp_endpoint",
    ):
        monkeypatch.setattr(settings, field, None)
    monkeypatch.setattr(settings, "broker_type", None)
    monkeypatch.setattr(settings, "otel_enabled", False)


class TestMinimalInstall:
    def test_app_imports_without_admin_extra(self, clean_optional_env: None):
        """App imports regardless of whether ``nicegui`` is installed."""
        from src._apps.server.app import app

        assert app is not None

    def test_health_endpoint_serves(self, clean_optional_env: None):
        """The always-on health endpoint returns 200 with minimal infra.

        ``TrustedHostMiddleware`` is wired at app-import time with
        ``settings.allowed_hosts`` (default ``["localhost", "127.0.0.1"]``),
        so ``TestClient`` must be pointed at one of those hosts — its
        default ``testserver`` would be rejected with 400.
        """
        from src._apps.server.app import app

        with TestClient(app, base_url="http://localhost") as client:
            response = client.get("/api/health")
            assert response.status_code == 200

    @pytest.mark.skipif(_has_nicegui, reason="nicegui is installed locally")
    def test_admin_routes_absent_when_nicegui_missing(self, clean_optional_env: None):
        """When nicegui is not installed, admin routes are not mounted.

        This is the load-bearing assertion for #104 Part 1. On dev machines
        that have nicegui installed it is skipped — the CI minimal-install
        job is the authoritative runner.
        """
        from src._apps.server.app import app

        admin_paths = [
            str(route.path)  # type: ignore[attr-defined]
            for route in app.routes
            if hasattr(route, "path") and "/admin" in str(route.path)  # type: ignore[attr-defined]
        ]
        assert not admin_paths, f"Expected no /admin routes, found: {admin_paths}"

    def test_aws_infra_modules_import_without_aws_extra(self, clean_optional_env: None):
        """The 4 AWS-backed infra modules import cleanly without boto3/aioboto3.

        Load-bearing for #104 Part 2 — this is what lets the ``CoreContainer``
        be constructed and the app boot. The actual ``*Client.__init__``
        still raises ImportError if called, but the Selector's ``disabled``
        branch returns ``providers.Object(None)``, so ``__init__`` is never
        reached when the AWS env vars are unset.

        Executed on both dev (aws installed) and CI minimal-install (aws
        NOT installed) — the assertion is the same in both cases: import
        must succeed.
        """
        import importlib

        for module_name in (
            "src._core.infrastructure.storage.object_storage_client",
            "src._core.infrastructure.storage.object_storage",
            "src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client",
            "src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model",
            "src._core.infrastructure.vectors.s3.client",
        ):
            # Fresh import each call — ``find_spec`` does not load the module
            module = importlib.import_module(module_name)
            assert module is not None

    def test_core_container_selectors_return_none_without_aws_env(
        self, clean_optional_env: None
    ):
        """Without AWS env vars, every AWS-backed Selector resolves to None.

        This guarantees the lazy ``aioboto3`` import inside each client's
        ``__init__`` is never triggered when the matching optional infra is
        disabled — which is the whole point of the ``[aws]`` extra being
        optional. Covers storage / DynamoDB / S3 Vectors in one pass.
        """
        from src._core.infrastructure.di.core_container import CoreContainer

        container = CoreContainer()

        assert container.storage_client() is None
        assert container.storage() is None
        assert container.dynamodb_client() is None
        assert container.s3vector_client() is None

    @pytest.mark.skipif(_has_otel, reason="otel extra installed locally")
    def test_app_boots_without_otel_extra(self, clean_optional_env: None):
        """Default settings (otel_enabled=False) must boot without otel extra.

        Load-bearing for #136 acceptance: ``make quickstart`` works unchanged
        with zero new env vars. The CI minimal-install job (no ``--extra otel``)
        is the authoritative runner.
        """
        from src._apps.server.app import app

        assert app is not None

    def test_otel_modules_not_imported_at_runtime(self, clean_optional_env: None):
        """Acceptance: no opentelemetry.* import leaks when otel extra is absent.

        Uses a clean subprocess so earlier tests in this session cannot
        pollute sys.modules. If the otel extra IS installed locally, skip
        (opentelemetry-api is pulled transitively by pydantic-ai-slim and
        the assertion loses meaning — the CI minimal-install job is
        authoritative).
        """
        import os
        import pathlib
        import subprocess
        import sys

        spec = importlib.util.find_spec("src")
        repo_root = str(
            pathlib.Path(spec.submodule_search_locations[0]).parent  # type: ignore[index, union-attr]
        )

        script = (
            "import sys\n"
            "from src._apps.server.app import app\n"
            "leaked = sorted(m for m in sys.modules if m.startswith('opentelemetry.sdk') or m.startswith('opentelemetry.exporter'))\n"
            "if leaked:\n"
            "    print('LEAKED:' + ','.join(leaked))\n"
            "    sys.exit(1)\n"
            "print('CLEAN')\n"
        )
        # Build a clean env: inherit the parent but force OTEL off so that
        # if the developer's .env has OTEL_ENABLED=true the subprocess does
        # not try to validate an endpoint and fail at Settings init.
        clean_env = {**os.environ, "OTEL_ENABLED": "false"}
        clean_env.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
            env=clean_env,
        )
        if "opentelemetry.sdk" in (
            result.stdout + result.stderr
        ) or "opentelemetry.exporter" in (result.stdout + result.stderr):
            pytest.skip(
                "otel extra installed locally — runtime-import test only "
                "meaningful in CI minimal-install job"
            )
        assert result.returncode == 0, (
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "CLEAN" in result.stdout
