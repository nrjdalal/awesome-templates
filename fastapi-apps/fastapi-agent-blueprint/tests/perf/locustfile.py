"""Locust performance-test harness for the FastAPI Agent Blueprint.

Run headless against the zero-config quickstart server::

    make quickstart      # terminal 1
    make perf-test       # terminal 2

Scenarios (see docs/operations/performance-locust.md):

- ``CustomerAuthUser`` (always on) — register a unique customer account, then
  exercise ``GET /v1/auth/me`` and token refresh on the customer JWT realm.
- ``HealthCheckUser`` (always on) — concurrent reads of ``GET /health`` (no-op
  baseline) and ``GET /health/db`` (pool acquisition + a real ``SELECT 1``).
- ``AdminCrudUser`` (opt-in) — admin-realm login, then the ``/v1/user`` CRUD
  cycle. Activated only when ``LOCUST_ADMIN_USERNAME`` and
  ``LOCUST_ADMIN_PASSWORD`` are both set; the bootstrap ``admin`` account
  cannot be used (setup-only — see the docs for one-time provisioning).

Numbers produced by this harness are illustrative for the local quickstart
setup only; adopters should rerun it against their own infrastructure.
"""

import logging
import os
import secrets
import uuid

from locust import HttpUser, between, task
from locust.exception import StopUser

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("LOCUST_ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("LOCUST_ADMIN_PASSWORD", "")
ADMIN_SCENARIO_ENABLED = bool(ADMIN_USERNAME and ADMIN_PASSWORD)

if not ADMIN_SCENARIO_ENABLED:
    logger.warning(
        "LOCUST_ADMIN_USERNAME / LOCUST_ADMIN_PASSWORD not set — the admin "
        "/v1/user CRUD scenario is disabled; running customer + health "
        "scenarios only."
    )


def _unique_name(prefix: str) -> str:
    """Collision-safe username that fits the 20-char schema limit."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error_code(response) -> str:
    """API errorCode for failure messages — never echo the response body.

    Bodies can carry submitted values in dev-mode error details, and unique
    bodies would fragment Locust's error table into one row per occurrence.
    """
    try:
        return str(response.json().get("errorCode", ""))
    except (ValueError, AttributeError):
        return ""


class CustomerAuthUser(HttpUser):
    """Customer-realm flow: one-time register, then profile reads + refresh."""

    weight = 3
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        username = _unique_name("perf")
        payload = {
            "username": username,
            "fullName": "Perf Customer",
            "email": f"{username}@example.com",
            "password": secrets.token_urlsafe(12),
        }
        with self.client.post(
            "/v1/auth/register", json=payload, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"customer register failed "
                    f"({response.status_code} {_error_code(response)})"
                )
                raise StopUser()
            data = response.json()["data"]
            self._access_token = data["accessToken"]
            self._refresh_token = data["refreshToken"]

    def on_stop(self) -> None:
        # Revoke the final refresh token so runs do not accumulate live
        # sessions. on_stop also runs when on_start failed, hence the guard.
        refresh_token = getattr(self, "_refresh_token", None)
        if refresh_token:
            self.client.post("/v1/auth/logout", json={"refreshToken": refresh_token})

    @task(3)
    def get_me(self) -> None:
        self.client.get("/v1/auth/me", headers=_bearer(self._access_token))

    @task(1)
    def refresh_tokens(self) -> None:
        with self.client.post(
            "/v1/auth/refresh",
            json={"refreshToken": self._refresh_token},
            catch_response=True,
        ) as response:
            if response.status_code in (401, 403):
                # The refresh token is dead (revoked/expired) — retrying it
                # forever would only stack failures, so stop this user.
                response.failure(
                    f"refresh token no longer valid "
                    f"({response.status_code} {_error_code(response)}) — "
                    "stopping this user"
                )
                self._refresh_token = None
                raise StopUser()
            if response.status_code != 200:
                response.failure(
                    f"token refresh failed "
                    f"({response.status_code} {_error_code(response)})"
                )
                return
            data = response.json()["data"]
            self._access_token = data["accessToken"]
            self._refresh_token = data["refreshToken"]


class HealthCheckUser(HttpUser):
    """Concurrent unauthenticated reads against the health endpoints."""

    weight = 2
    wait_time = between(0.2, 1.0)

    @task(5)
    def health(self) -> None:
        self.client.get("/health")

    @task(1)
    def health_db(self) -> None:
        # Not a no-op: acquires a pool connection and runs SELECT 1 (503 when
        # the database is unreachable).
        self.client.get("/health/db")


class AdminCrudUser(HttpUser):
    """Admin-realm /v1/user CRUD cycle. Spawned only when credentials are set.

    Locust skips user classes with ``abstract = True`` at collection time, so
    without credentials this scenario never spawns and the default run stays
    zero-setup. Invalid credentials fail loudly in the stats table instead.
    """

    abstract = not ADMIN_SCENARIO_ENABLED
    weight = 1
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        with self.client.post(
            "/v1/admin/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"admin login rejected ({response.status_code}) — check "
                    "LOCUST_ADMIN_USERNAME / LOCUST_ADMIN_PASSWORD (bootstrap "
                    "and temp-password admins cannot use the token API)"
                )
                raise StopUser()
            data = response.json()["data"]
            self._access_token = data["accessToken"]
            self._refresh_token = data["refreshToken"]

    def on_stop(self) -> None:
        # Mirror CustomerAuthUser: revoke the admin refresh token so opt-in
        # runs don't leave live admin sessions behind (on_stop also runs when
        # on_start failed, hence the guard).
        refresh_token = getattr(self, "_refresh_token", None)
        if refresh_token:
            self.client.post("/v1/admin/logout", json={"refreshToken": refresh_token})

    @task(2)
    def list_users(self) -> None:
        self.client.get(
            "/v1/users",
            params={"page": 1, "pageSize": 10},
            headers=_bearer(self._access_token),
        )

    @task(1)
    def user_crud_cycle(self) -> None:
        headers = _bearer(self._access_token)
        username = _unique_name("crud")
        create = self.client.post(
            "/v1/user",
            json={
                "username": username,
                "fullName": "Perf Crud",
                "email": f"{username}@example.com",
                "password": secrets.token_urlsafe(12),
            },
            headers=headers,
        )
        if create.status_code != 200:
            return
        user_id = create.json()["data"]["id"]
        try:
            self.client.get(
                f"/v1/user/{user_id}", headers=headers, name="/v1/user/[id]"
            )
            self.client.put(
                f"/v1/user/{user_id}",
                json={"fullName": "Perf Crud Updated"},
                headers=headers,
                name="/v1/user/[id]",
            )
        finally:
            # Always try to remove the record so repeated runs do not
            # accumulate rows (a hard abort can still leave residue).
            self.client.delete(
                f"/v1/user/{user_id}", headers=headers, name="/v1/user/[id]"
            )
