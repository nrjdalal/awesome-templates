"""Copy-flow smoke test — every example must survive cp-to-src (issue #260).

The documented activation flow for every example is::

    cp -r examples/<name> src/<name>
    make quickstart

Unit tests exercise examples in their ``examples.*`` layout, so a broken
copy-flow (absolute self-imports, ``wire(packages=[...])`` string paths,
duplicate table registration) ships with green CI — this test closes that
gap by booting each example in the copied layout and probing a real
endpoint.

Isolation strategy (see tests/integration/_core/test_minimal_install.py for
the subprocess precedent):

- Build a **shadow tree** in tmp: copy the repo's ``src/`` plus the example
  domain dir(s). The real working tree is never touched, so a crashed run
  leaves no residue.
- Run the probe in a **fresh subprocess** via ``python -c`` with
  ``cwd=<tmp>``: ``-c`` puts the cwd first on ``sys.path``, so ``import
  src`` resolves to the shadow copy, and the repo root is *not* on the
  path — a leftover absolute ``examples.*`` import fails loudly instead of
  silently binding the wrong class objects. ``discover_domains()`` scans the
  directory of the imported ``src`` package, i.e. the shadow tree.
- ``ENV=quickstart`` triggers ``Base.metadata.create_all`` on boot; the
  sqlite file lives in tmp (never ``:memory:`` — the process holds several
  engines and each ``:memory:`` connection would get its own empty DB).
- Optional-infra env vars are scrubbed so a developer shell with real LLM
  keys can never flip a chatbot Selector to ``real`` and bill an API call.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

_SCRUB_PREFIXES = (
    "LLM_",
    "EMBEDDING_",
    "DYNAMODB_",
    "S3VECTORS_",
    "STORAGE_",
    "OTEL_",
    "DATABASE_",
    "SQS_",
    "RABBITMQ_",
    "BROKER_",
)

# Executed via `python -c` inside the shadow tree. Probes arrive as JSON in
# EXAMPLES_SMOKE_PROBES; any non-200 status or missing expected value exits 1
# with diagnostics on stdout. A probe may set `retry_seconds` for eventually-
# consistent state (e.g. an InMemory worker task finishing in the background):
# TestClient runs the app loop in a worker thread, so `time.sleep` here lets
# the background task progress between attempts.
_RUNNER = """
import json, os, sys, time, traceback

probes = json.loads(os.environ["EXAMPLES_SMOKE_PROBES"])
try:
    from fastapi.testclient import TestClient

    from src._apps.server.app import app

    with TestClient(app, base_url="http://localhost") as client:
        for probe in probes:
            method = probe["method"]
            path = probe["path"]
            key = probe.get("expect_key")
            deadline = time.monotonic() + float(probe.get("retry_seconds", 0))
            while True:
                resp = client.request(method, path, json=probe.get("json"))
                status_ok = resp.status_code == probe.get("expect_status", 200)
                data = {}
                if status_ok and key is not None:
                    data = resp.json().get("data") or {}
                value_ok = key is None or data.get(key) == probe["expect_value"]
                if status_ok and value_ok:
                    break
                if time.monotonic() >= deadline:
                    if not status_ok:
                        print("PROBE FAILED", method, path, resp.status_code)
                        print(resp.text[:800])
                    else:
                        print("VALUE MISMATCH", method, path, key)
                        print(
                            "got:", repr(data.get(key)),
                            "want:", repr(probe["expect_value"]),
                        )
                        print(json.dumps(data)[:800])
                    sys.exit(1)
                time.sleep(0.15)
    print("SMOKE OK")
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
    sys.exit(1)
"""


@dataclass(frozen=True)
class ExampleCase:
    id: str
    # (source dir relative to examples/, target package name under src/)
    copies: tuple[tuple[str, str], ...]
    probes: tuple[dict[str, Any], ...]


CASES = (
    ExampleCase(
        id="todo",
        copies=(("todo", "todo"),),
        probes=(
            {"method": "POST", "path": "/v1/todo", "json": {"title": "smoke"}},
            {
                "method": "GET",
                "path": "/v1/todo/1",
                "expect_key": "id",
                "expect_value": 1,
            },
        ),
    ),
    ExampleCase(
        id="url_shortener",
        copies=(("url_shortener", "url_shortener"),),
        probes=(
            {
                "method": "POST",
                "path": "/v1/link",
                "json": {"short_code": "abc", "target_url": "https://example.com"},
            },
            {
                "method": "GET",
                "path": "/v1/link/abc",
                "expect_key": "shortCode",
                "expect_value": "abc",
            },
        ),
    ),
    ExampleCase(
        id="webhook_receiver",
        copies=(("webhook_receiver", "webhook_receiver"),),
        probes=(
            {
                "method": "POST",
                "path": "/v1/webhook",
                "json": {"source": "stripe", "payload": {"k": "v"}},
            },
            # The InMemory broker runs the task in the request process, so a
            # completed status also proves the worker-task Provide wiring.
            # The task sleeps 0.2s in the background — poll until done.
            {
                "method": "GET",
                "path": "/v1/webhook/1",
                "expect_key": "status",
                "expect_value": "done",
                "retry_seconds": 10,
            },
        ),
    ),
    ExampleCase(
        id="simple_chatbot",
        copies=(("simple_chatbot", "simple_chatbot"),),
        probes=(
            {"method": "POST", "path": "/v1/chat", "json": {"prompt": "hello"}},
            {"method": "GET", "path": "/v1/chat/1"},
        ),
    ),
    ExampleCase(
        id="chatbot_with_guardrails",
        copies=(("chatbot_with_guardrails", "chatbot_with_guardrails"),),
        probes=({"method": "POST", "path": "/v1/chat", "json": {"prompt": "hello"}},),
    ),
    ExampleCase(
        id="chatbot_with_memory",
        copies=(("chatbot_with_memory", "chatbot_with_memory"),),
        probes=(
            {
                "method": "POST",
                "path": "/v1/chat/memory",
                "json": {"session_id": "s1", "prompt": "hello"},
            },
            {"method": "GET", "path": "/v1/chat/memory/s1"},
        ),
    ),
    ExampleCase(
        id="blog",
        copies=(("blog/author", "author"), ("blog/post", "post")),
        probes=(
            {"method": "POST", "path": "/v1/author", "json": {"display_name": "Ada"}},
            {
                "method": "POST",
                "path": "/v1/post",
                "json": {"author_id": 1, "title": "Hi", "body": "Body"},
            },
            # The cross-domain DIP payoff: post resolves the author name
            # through src.author — the exact surface that used to crash.
            {
                "method": "GET",
                "path": "/v1/post/1",
                "expect_key": "authorDisplayName",
                "expect_value": "Ada",
            },
        ),
    ),
)


def _tracked_top_level_examples() -> set[str]:
    result = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-z", "--", "examples"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    names: set[str] = set()
    for entry in result.stdout.split("\0"):
        parts = Path(entry).parts
        # examples/<name>/... — top-level files (README.md, __init__.py) are
        # not example dirs.
        if len(parts) >= 3 and parts[0] == "examples":
            names.add(parts[1])
    return names


def test_every_tracked_example_has_a_smoke_case() -> None:
    """Completeness guard: a new example must register a smoke case.

    Without this, a future examples/<name>/ lands, nobody extends CASES,
    and the "every example is booted post-copy" contract silently shrinks.
    Worker-only examples (no HTTP surface) must still add a case — extend
    the runner with a task-level probe when that need first arises.
    """
    covered = {
        Path(source_rel).parts[0] for case in CASES for source_rel, _ in case.copies
    }
    tracked = _tracked_top_level_examples()

    missing = tracked - covered
    assert not missing, (
        f"examples without a copy-flow smoke case: {sorted(missing)} — "
        "add an ExampleCase to CASES in this file."
    )

    stale = covered - tracked
    assert not stale, (
        f"smoke cases reference removed examples: {sorted(stale)} — "
        "drop the stale ExampleCase from CASES."
    )


def _build_shadow(tmp_path: Path, case: ExampleCase) -> None:
    shadow_src = tmp_path / "src"
    shutil.copytree(
        REPO_ROOT / "src",
        shadow_src,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for source_rel, target_name in case.copies:
        target = shadow_src / target_name
        # Fresh-clone fidelity: a developer may have the example copied into
        # their real src/ already — the shadow must model the documented
        # "fresh clone + cp" state, not their local mutation.
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(
            REPO_ROOT / "examples" / source_rel,
            target,
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def _smoke_env(tmp_path: Path, case: ExampleCase) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_SCRUB_PREFIXES)
    }
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "ENV": "quickstart",
            "DATABASE_ENGINE": "sqlite",
            "DATABASE_NAME": str(tmp_path / "smoke.db"),
            "DATABASE_USER": "unused",
            "DATABASE_PASSWORD": "unused",
            "DATABASE_HOST": "unused",
            "DATABASE_PORT": "0",
            "BROKER_TYPE": "inmemory",
            "VECTOR_STORE_TYPE": "inmemory",
            "OTEL_ENABLED": "false",
            "ADMIN_BOOTSTRAP_ENABLED": "false",
            "ADMIN_STORAGE_SECRET": "copyflow-smoke-local-only",
            "LOG_LEVEL": "WARNING",
            "EXAMPLES_SMOKE_PROBES": json.dumps(list(case.probes)),
        }
    )
    return env


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_example_survives_copy_to_src(case: ExampleCase, tmp_path: Path) -> None:
    _build_shadow(tmp_path, case)

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _RUNNER],
        cwd=tmp_path,
        env=_smoke_env(tmp_path, case),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0 and "SMOKE OK" in result.stdout, (
        f"copy-flow smoke failed for example {case.id!r}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
