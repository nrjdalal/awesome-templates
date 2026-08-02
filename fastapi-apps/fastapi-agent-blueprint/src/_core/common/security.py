"""Password hashing helpers.

bcrypt is deliberately slow — roughly 220 ms per operation at the default cost
on current hardware. That is the point for an attacker, and a problem for an
event loop: a synchronous call from ``async def`` blocks **every** concurrent
task in the process for the duration, health checks included. It is a
process-wide stall, not per-request latency.

So request-path callers use the ``*_async`` helpers, which run the work in a
worker thread. The synchronous helpers stay for callers that are not on a loop
(Alembic seeds, CLI tooling) — offloading there would only add overhead.
"""

from __future__ import annotations

import anyio.to_thread
import bcrypt

# Verifying against a throwaway digest is what makes the "principal not found"
# branch cost the same as a real check. Generated once at import: the value is
# never compared against anything real, only used to burn one bcrypt round.
_DUMMY_DIGEST = bcrypt.hashpw(b"unused-placeholder-input", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    """Synchronous hash. Use :func:`hash_password_async` on the request path."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Synchronous verify. Use :func:`verify_password_async` on the request path."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        # A malformed or truncated stored digest makes bcrypt raise rather than
        # return False. Failing closed keeps that a failed login instead of a 500.
        return False


async def hash_password_async(password: str) -> str:
    """Hash off the event loop."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verify off the event loop."""
    return await anyio.to_thread.run_sync(
        verify_password, plain_password, hashed_password
    )


async def verify_or_dummy(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a credential, paying the same cost when the principal is absent.

    The natural spelling of a login check —
    ``if principal is None or not verify_password(...)`` — short-circuits before
    bcrypt when the username is unknown, so an unknown account answers ~220 ms
    faster than a known one with a wrong password. That gap is remotely
    measurable and enumerates accounts.

    Passing ``None`` here still runs one verification, against a throwaway
    digest, and returns ``False``.
    """
    if not hashed_password:
        await verify_password_async(plain_password, _DUMMY_DIGEST)
        return False
    return await verify_password_async(plain_password, hashed_password)
