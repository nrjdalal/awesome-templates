"""The root `run_*_local.py` entrypoints must actually run what they announce.

`run_scheduler_local.py` called `run_scheduler(args)` without awaiting it, so
`make scheduler` printed `coroutine 'run_scheduler' was never awaited` and exited
0 having scheduled nothing — `audit_cleanup_task` (`0 3 * * *`, the audit-log
retention DELETE) never fired from the path the docs point at. The file's own
docstring explains how: it "mirrors `run_worker_local.py`", and it did so
literally, but taskiq's `run_worker` is sync while `run_scheduler` is a coroutine
function.

Found by extending pyright over the repo root (#375) — `reportUnusedCoroutine`.
Nothing else could see it: the runners are excluded from the test suite, and a
never-awaited coroutine is a warning, not an error, so the process exits 0.

These tests pin the two halves that made it silent: that the wrapper awaits, and
that the upstream function is still the shape the wrapper assumes.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    """Import a root-level runner, which is a script rather than a package."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestSchedulerRunner:
    def test_taskiq_run_scheduler_is_still_a_coroutine_function(self) -> None:
        """The assumption the wrapper is built on.

        If taskiq ever makes this sync, `asyncio.run` starts raising instead of
        silently no-opping — this test says which side changed.
        """
        from taskiq.cli.scheduler.run import run_scheduler

        assert inspect.iscoroutinefunction(run_scheduler)

    def test_main_awaits_the_scheduler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        module = _load("run_scheduler_local")
        awaited: list[Any] = []

        async def _fake_run_scheduler(args: Any) -> None:
            awaited.append(args)

        monkeypatch.setattr(module, "run_scheduler", _fake_run_scheduler)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            module.main()

        assert awaited, (
            "main() returned without awaiting run_scheduler — the scheduler "
            "process would exit 0 having scheduled nothing"
        )
        never_awaited = [w for w in caught if "never awaited" in str(w.message)]
        assert not never_awaited, [str(w.message) for w in never_awaited]

    def test_scheduler_args_point_at_the_scheduler_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A correctly-awaited call to the wrong target is the same outage."""
        module = _load("run_scheduler_local")
        seen: list[Any] = []

        async def _capture(args: Any) -> None:
            seen.append(args)

        monkeypatch.setattr(module, "run_scheduler", _capture)
        module.main()

        (args,) = seen
        assert args.scheduler == "src._apps.worker.scheduler:scheduler"
        assert "src._apps.worker.scheduler" in args.modules


class TestWorkerRunner:
    def test_a_failed_worker_start_becomes_a_non_zero_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`run_worker` returns a status code; discarding it always exited 0."""
        module = _load("run_worker_local")
        monkeypatch.setattr(
            module, "ensure_worker_capable_broker", lambda _broker: None
        )
        monkeypatch.setattr(module, "run_worker", lambda _args: 3)

        with pytest.raises(SystemExit) as info:
            module.main()

        assert info.value.code == 3

    def test_a_clean_worker_exit_stays_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = _load("run_worker_local")
        monkeypatch.setattr(
            module, "ensure_worker_capable_broker", lambda _broker: None
        )
        monkeypatch.setattr(module, "run_worker", lambda _args: None)

        with pytest.raises(SystemExit) as info:
            module.main()

        assert info.value.code is None, "SystemExit(None) is a 0 exit"
