"""Contract tests for the shared password helper (#322).

Two properties are pinned here because both are invisible to a functional test:

1. The bcrypt work must not run on the event loop. bcrypt is deliberately slow
   (~220 ms measured), so a synchronous call from ``async def`` stalls **every**
   concurrent task in the process, health checks included — it is not per-request
   latency.
2. Verification must cost the same whether or not the principal exists, so an
   unauthenticated caller cannot enumerate usernames by timing the response.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from src._core.common import security


class TestPasswordHelperIsAwaitable:
    """The async API is what callers must use; the sync one stays for tooling."""

    async def test_hash_and_verify_round_trip(self):
        raw = uuid.uuid4().hex
        digest = await security.hash_password_async(raw)
        assert await security.verify_password_async(raw, digest) is True
        assert await security.verify_password_async(uuid.uuid4().hex, digest) is False

    async def test_hash_does_not_block_the_event_loop(self):
        """A concurrent 10 ms heartbeat must keep ticking while a hash runs.

        Without offloading, the worst tick equals the bcrypt cost (~220 ms) and
        every other request on the worker is frozen for that long.
        """
        ticks: list[float] = []

        async def heartbeat() -> None:
            try:
                while True:
                    started = time.perf_counter()
                    await asyncio.sleep(0.01)
                    ticks.append((time.perf_counter() - started) * 1000)
            except asyncio.CancelledError:
                pass

        beat = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.05)
        await security.hash_password_async(uuid.uuid4().hex)
        await asyncio.sleep(0.05)
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)

        assert ticks, "heartbeat never ran"
        # bcrypt costs ~220 ms; a 100 ms ceiling fails loudly if the offload is
        # removed while staying far above normal scheduler jitter.
        assert max(ticks) < 100, (
            f"event loop stalled for {max(ticks):.1f} ms during hashing — "
            "the bcrypt call is running on the loop"
        )

    async def test_verify_does_not_block_the_event_loop(self):
        raw = uuid.uuid4().hex
        digest = await security.hash_password_async(raw)
        ticks: list[float] = []

        async def heartbeat() -> None:
            try:
                while True:
                    started = time.perf_counter()
                    await asyncio.sleep(0.01)
                    ticks.append((time.perf_counter() - started) * 1000)
            except asyncio.CancelledError:
                pass

        beat = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.05)
        await security.verify_password_async(raw, digest)
        await asyncio.sleep(0.05)
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)

        assert max(ticks) < 100, (
            f"event loop stalled for {max(ticks):.1f} ms during verification"
        )


class TestConstantWorkOnTheMissPath:
    """`verify_or_dummy` must pay the bcrypt cost even with no stored digest.

    `if principal is None or not verify_password(...)` short-circuits before
    bcrypt on the miss path, so an unknown username answers ~220 ms faster than a
    wrong password. That difference is remotely measurable and enumerates accounts.
    """

    async def test_absent_principal_still_costs_a_verification(self):
        digest = await security.hash_password_async(uuid.uuid4().hex)

        async def timed(stored: str | None) -> float:
            started = time.perf_counter()
            await security.verify_or_dummy("guess", stored)
            return (time.perf_counter() - started) * 1000

        absent = min([await timed(None) for _ in range(3)])
        present = min([await timed(digest) for _ in range(3)])

        # Both paths run one bcrypt operation, so the gap must be a small
        # fraction of the ~220 ms a skipped verification would save.
        assert abs(present - absent) < present * 0.5, (
            f"timing side channel: absent={absent:.1f} ms present={present:.1f} ms"
        )

    async def test_absent_principal_returns_false(self):
        assert await security.verify_or_dummy("anything", None) is False

    async def test_present_principal_still_verifies_correctly(self):
        raw = uuid.uuid4().hex
        digest = await security.hash_password_async(raw)
        assert await security.verify_or_dummy(raw, digest) is True
        assert await security.verify_or_dummy(uuid.uuid4().hex, digest) is False


class TestSyncHelpersRemain:
    """The sync helpers stay importable — Alembic seeds and CLI tooling use them
    outside an event loop, where offloading would be pointless."""

    def test_sync_round_trip(self):
        raw = uuid.uuid4().hex
        assert security.verify_password(raw, security.hash_password(raw)) is True


@pytest.mark.parametrize("stored", ["", "not-a-bcrypt-digest"])
async def test_verify_or_dummy_tolerates_a_malformed_digest(stored):
    """A corrupted stored value must fail closed, not raise — bcrypt raises
    ValueError on a malformed salt, which would surface as a 500 on login."""
    assert await security.verify_or_dummy("guess", stored) is False
