"""The work ledger under concurrent writers in one tree (ADR052-G4).

Every update helper in ``.agents/shared/work_ledger.py`` reads the whole ledger,
changes a field and writes the whole ledger back. Nothing serialised that, and the
write was a truncating ``write_text``. So two processes in one tree — a
UserPromptSubmit hook racing a Stop hook, a skill racing a hook, two sessions in
one checkout — lost each other's updates, and a reader that caught the file
between the truncate and the write got ``None`` from ``read_ledger`` and wrote a
*default* ledger back. Measured on the code before the fix with a scratch probe of
seven processes, one field each: six of the seven fields ended ``None`` in three
runs out of three, and a reader caught a partial file on about one read in ten.
(PR #428's review deferred this as R7, once each worktree had its own ledger.)

The fix has two halves, and each race test here needs a specific one:

* the lock keeps every update — with the atomic write alone, about 170 of the
  200 appends in ``test_concurrent_updates_lose_nothing`` disappear;
* the atomic replace keeps readers whole — with the lock alone, the readers in
  ``test_a_reader_never_sees_a_partial_ledger`` still catch a partial file
  several times in every run.

The racing processes are subprocesses, so the module-collision rule in
``docs/ai/shared/test-patterns.md`` § Harness Hook Tests does not reach them —
each has its own ``sys.modules``. Every child gets ``HARNESS_STATE_ROOT`` inside
``tmp_path``, so the ledger it races on is never the operator's.
"""

from __future__ import annotations

import contextlib
import errno
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import work_ledger as wl

_SHARED = Path(__file__).resolve().parents[3] / ".agents" / "shared"

needs_flock = pytest.mark.skipif(
    importlib.util.find_spec("fcntl") is None,
    reason="advisory file locks are POSIX-only",
)

# Each child imports the module, says so, then blocks reading stdin. They all
# share one pipe as stdin, so closing its write end releases every child with a
# single EOF: a barrier, not a staggered start that lets the first child finish
# before the last one has begun.
_PRELUDE = f"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, {str(_SHARED)!r})
import work_ledger as wl
print("ready", flush=True)
sys.stdin.read()
"""


def _ledger_path(state_root: Path) -> Path:
    return state_root / ".agents" / "state" / "current-work.json"


def _lock_path(state_root: Path) -> Path:
    return _ledger_path(state_root).with_name("current-work.json.lock")


def _on_disk(state_root: Path) -> dict:
    return json.loads(_ledger_path(state_root).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _module_defaults_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In-process calls without ``state_root`` land in ``tmp_path``, like the children's."""
    monkeypatch.setattr(wl, "STATE_DIR", _ledger_path(tmp_path).parent)
    monkeypatch.setattr(wl, "LEDGER_PATH", _ledger_path(tmp_path))


@contextlib.contextmanager
def _released_together(
    scripts: list[str], state_root: Path
) -> Iterator[list[subprocess.Popen[str]]]:
    """One child per script, all parked at the barrier, then released at once."""
    env = {**os.environ, "HARNESS_STATE_ROOT": str(state_root)}
    read_end, write_end = os.pipe()
    procs: list[subprocess.Popen[str]] = []
    try:
        for script in scripts:
            procs.append(
                subprocess.Popen(  # noqa: S603
                    [sys.executable, "-c", _PRELUDE + script],
                    stdin=read_end,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
            )
        os.close(read_end)
        read_end = -1
        for proc in procs:
            assert proc.stdout is not None
            if proc.stdout.readline() != "ready\n":
                pytest.fail(
                    f"a child never reached the barrier:\n{proc.communicate()[1]}"
                )
        os.close(write_end)
        write_end = -1
        yield procs
    finally:
        for fd in (read_end, write_end):
            if fd != -1:
                os.close(fd)
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def _outputs(procs: list[subprocess.Popen[str]]) -> list[str]:
    outputs = []
    for proc in procs:
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
        outputs.append(out)
    return outputs


# ---------------------------------------------------------------------------
# Nothing is lost
# ---------------------------------------------------------------------------


@needs_flock
def test_concurrent_updates_lose_nothing(tmp_path: Path) -> None:
    """Eight processes append 25 ids each to a fresh tree; all 200 survive, once.

    Appending makes every single lost update visible — the public helpers only
    overwrite fixed fields, where a later write hides an earlier loss — so this
    drives the primitive they all share. Nothing is seeded: the first updates
    also have to create the state directory and the lock file between them.
    """
    processes, rounds = 8, 25
    script = """
for i in range({rounds}):
    appended = wl._update_ledger(
        lambda ledger, i=i: ledger["workflow"]["tasks"].append({{"id": "{n}:%d" % i}}),
        updated_by="test:append",
        state_root=None,
    )
    assert appended, "update {n}:%d was dropped waiting for the lock" % i
"""
    scripts = [script.format(rounds=rounds, n=n) for n in range(processes)]

    with _released_together(scripts, tmp_path) as procs:
        _outputs(procs)

    ids = sorted(task["id"] for task in _on_disk(tmp_path)["workflow"]["tasks"])
    assert ids == sorted(f"{n}:{i}" for n in range(processes) for i in range(rounds))
    # Two hundred contended replaces left no temporary file behind.
    assert sorted(p.name for p in _ledger_path(tmp_path).parent.iterdir()) == [
        "current-work.json",
        "current-work.json.lock",
    ]


# One process per field, each through a different public helper: the field it
# owns, the call that writes round ``i``, and what that call leaves there. The
# hook-side helpers get an explicit ``state_root`` and the skill-side ones the
# module default, so both spellings have to reach one ledger and one lock.
_HELPER_RACE: list[tuple[tuple[str, ...], str, Callable[[int], object]]] = [
    (
        ("last_prompt",),
        "wl.update_last_prompt(f'prompt {i}', state_root=ROOT)",
        lambda i: f"prompt {i}",
    ),
    (("goal",), "wl.update_goal_scope_plan(goal=f'goal {i}')", lambda i: f"goal {i}"),
    (
        ("scope",),
        "wl.update_goal_scope_plan(scope=f'scope {i}')",
        lambda i: f"scope {i}",
    ),
    (("plan",), "wl.update_goal_scope_plan(plan=f'plan {i}')", lambda i: f"plan {i}"),
    (
        ("workflow", "current_task"),
        "wl.update_workflow_state(current_task=f'task {i}')",
        lambda i: f"task {i}",
    ),
    (
        ("workflow", "plan_ref"),
        "wl.update_workflow_state(plan_ref=f'ref {i}')",
        lambda i: f"ref {i}",
    ),
    (
        ("verification", "last_command"),
        "wl.mark_verified(f'pytest {i}', passed=False, state_root=ROOT)",
        lambda i: f"pytest {i}",
    ),
    (
        ("verification", "changed_py_files"),
        "wl._changed_py_files = lambda repo_root=None: [f'src/{i}.py']\n"
        "    wl.update_verification_from_git(state_root=ROOT)",
        lambda i: [f"src/{i}.py"],
    ),
]


@needs_flock
def test_each_update_helper_keeps_the_others_fields(tmp_path: Path) -> None:
    """Eight helpers racing on one ledger each leave their own last value.

    On the code before the fix this failed at its first field, ``last_prompt``
    ending ``None`` — lost not to a stale snapshot but to the default ledger a
    torn read turns into. With the lock removed it fails on a stale snapshot.
    """
    rounds = 40
    scripts = [
        f"ROOT = Path({str(tmp_path)!r})\nfor i in range({rounds}):\n    {call}\n"
        for _, call, _ in _HELPER_RACE
    ]

    with _released_together(scripts, tmp_path) as procs:
        _outputs(procs)

    ledger = _on_disk(tmp_path)
    for keys, _, expected in _HELPER_RACE:
        value: object = ledger
        for key in keys:
            assert isinstance(value, dict)
            value = value[key]
        assert value == expected(rounds - 1), keys


# ---------------------------------------------------------------------------
# No reader sees a partial file
# ---------------------------------------------------------------------------


def test_a_reader_never_sees_a_partial_ledger(tmp_path: Path) -> None:
    """Readers racing two writers parse a complete ledger on every read.

    The readers read the file the way ``read_ledger`` and the stage gate do —
    without the lock — and a 256 KiB ``plan`` makes each write long enough that
    a truncating one is caught half-done on every run. The writers keep writing
    until every reader has seen one of their versions, so no reader can finish
    having read only before or only after them.
    """
    size, readers = 256 * 1024, 3
    assert wl.write_ledger(wl._default_ledger(), state_root=tmp_path)
    done = tmp_path / "writers-done"
    saw = [tmp_path / f"reader-{k}-saw-a-write" for k in range(readers)]

    writer = f"""
saw = [Path(p) for p in {[str(p) for p in saw]!r}]
deadline = time.monotonic() + 30
i = 0
while (i < 60 or not all(p.exists() for p in saw)) and time.monotonic() < deadline:
    wl.update_goal_scope_plan(plan="{{w}}%04d:" % i + "x" * {size})
    i += 1
"""
    reader = f"""
path, done = Path({str(_ledger_path(tmp_path))!r}), Path({str(done)!r})
saw = Path({{saw!r}})
torn = []
while not done.exists():
    text = path.read_text(encoding="utf-8")
    try:
        plan = json.loads(text)["plan"]
    except (ValueError, KeyError, TypeError):
        torn.append(len(text))
        continue
    if plan is not None and not saw.exists():
        saw.touch()
print(json.dumps(torn))
"""
    scripts = [writer.format(w=w) for w in "ab"]
    scripts += [reader.format(saw=str(p)) for p in saw]

    with _released_together(scripts, tmp_path) as procs:
        _outputs(procs[:2])
        done.touch()
        torn = [json.loads(out) for out in _outputs(procs[2:])]

    assert torn == [[]] * readers, (
        "a reader parsed a partial ledger (the lengths it read are listed)"
    )
    assert all(p.exists() for p in saw), "a reader never overlapped the writers"


# ---------------------------------------------------------------------------
# Degrade, never hang
# ---------------------------------------------------------------------------


@needs_flock
def test_an_update_waits_for_a_stuck_holder_then_drops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A holder that never lets go costs one update the timeout, and that update.

    Dropped rather than written unlocked: the holder is still running, so writing
    anyway would put one of the two updates on top of the other.
    """
    import fcntl

    wl.update_last_prompt("kept", state_root=tmp_path)
    monkeypatch.setattr(wl, "_LOCK_TIMEOUT_S", 0.3)
    held = os.open(_lock_path(tmp_path), os.O_RDWR)
    fcntl.flock(held, fcntl.LOCK_EX)
    try:
        started = time.monotonic()
        wl.update_last_prompt("dropped", state_root=tmp_path)
        waited = time.monotonic() - started
    finally:
        os.close(held)

    assert 0.3 <= waited < 5, waited
    assert _on_disk(tmp_path)["last_prompt"] == "kept"


def test_an_update_runs_unlocked_without_fcntl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Off POSIX the update still lands — atomically, but unserialised."""
    monkeypatch.setitem(sys.modules, "fcntl", None)

    wl.mark_verified("pytest", passed=True, state_root=tmp_path)

    assert _on_disk(tmp_path)["verification"]["status"] == "passed"
    assert not _lock_path(tmp_path).exists()


def _flock_failing_with(code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    import fcntl

    def fail(fd: int, operation: int) -> None:
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(fcntl, "flock", fail)


@needs_flock
@pytest.mark.parametrize(
    "code", sorted({errno.ENOTSUP, errno.EOPNOTSUPP}), ids=errno.errorcode.get
)
def test_an_update_runs_unlocked_where_flock_is_unsupported(
    code: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the filesystem has no flock, nobody can hold the lock: run unlocked."""
    _flock_failing_with(code, monkeypatch)

    wl.update_goal_scope_plan(goal="unlocked")

    assert _on_disk(tmp_path)["goal"] == "unlocked"


@needs_flock
def test_eacces_from_flock_counts_as_a_held_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where Python emulates ``flock`` with ``fcntl(F_SETLK)``, a conflict is EACCES.

    Read as "unsupported", it would let the update run unlocked beside the holder.
    """
    wl.update_goal_scope_plan(goal="kept")
    monkeypatch.setattr(wl, "_LOCK_TIMEOUT_S", 0.2)
    _flock_failing_with(errno.EACCES, monkeypatch)

    started = time.monotonic()
    wl.update_goal_scope_plan(goal="dropped")
    waited = time.monotonic() - started

    assert 0.2 <= waited < 5, waited
    assert _on_disk(tmp_path)["goal"] == "kept"


@needs_flock
@pytest.mark.parametrize(
    "code",
    [errno.EPERM, errno.ENOSYS, errno.ENOLCK, errno.EINVAL, errno.EIO],
    ids=errno.errorcode.get,
)
def test_a_flock_error_that_proves_nothing_drops_the_update(
    code: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An error that says nothing about other writers neither writes nor raises.

    EPERM and ENOSYS are a sandbox denying *this* caller, and ENOLCK a full lock
    table or a failed remote lock manager: none means nobody else holds the lock.
    """
    wl.update_goal_scope_plan(goal="kept")
    _flock_failing_with(code, monkeypatch)

    wl.update_goal_scope_plan(goal="dropped")

    assert _on_disk(tmp_path)["goal"] == "kept"


@needs_flock
def test_a_lock_file_this_caller_cannot_open_drops_the_update(tmp_path: Path) -> None:
    """Another writer may hold a lock file that only this caller cannot open."""
    wl.update_goal_scope_plan(goal="kept")
    lock = _lock_path(tmp_path)
    lock.unlink()
    lock.mkdir()  # os.open(..., O_RDWR) on a directory fails, as root too

    wl.update_goal_scope_plan(goal="dropped")

    assert _on_disk(tmp_path)["goal"] == "kept"


@needs_flock
def test_a_failed_change_writes_nothing_and_frees_the_lock(tmp_path: Path) -> None:
    import fcntl

    def half_done(ledger: dict) -> None:
        ledger["goal"] = "half-done"
        raise RuntimeError

    with pytest.raises(RuntimeError):
        wl._update_ledger(half_done, updated_by="test", state_root=tmp_path)

    assert not _ledger_path(tmp_path).exists()
    fd = os.open(_lock_path(tmp_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises if still held
    finally:
        os.close(fd)


def test_a_failed_write_keeps_the_previous_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that cannot be swapped in changes nothing and leaves no temp file."""
    wl.update_goal_scope_plan(goal="before")
    before = _ledger_path(tmp_path).read_bytes()

    def refuse(src: object, dst: object) -> None:
        raise OSError(errno.EXDEV, "Cross-device link")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", refuse)
        assert wl.write_ledger({**wl._default_ledger(), "goal": "after"}) is False

    assert _ledger_path(tmp_path).read_bytes() == before
    assert not list(_ledger_path(tmp_path).parent.glob("*.tmp"))
