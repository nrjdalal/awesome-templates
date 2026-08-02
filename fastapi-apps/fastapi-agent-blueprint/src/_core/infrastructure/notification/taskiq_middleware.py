"""Taskiq middleware that alerts on terminal task failures (#310).

The HTTP surface dispatches from the global exception handlers
(``src/_core/exceptions/exception_handlers.py``). A worker task has neither a
request nor a status code, so this middleware supplies what ``ErrorNotifier``
needs while reusing the same gating knobs:

- **Synthetic severity** — ``BaseCustomException`` contributes its own
  ``status_code``; anything else counts as 500. This keeps
  ``NOTIFICATION_SEVERITY_THRESHOLD`` meaningful for the worker instead of
  introducing a second severity model (the alternative #310 weighed and
  rejected: bypassing the threshold would leave operators no off switch short
  of unsetting the provider).
- **Task-scoped cooldown key** — a bare code would let one noisy task suppress
  every other task's alert for the whole cooldown window, so this middleware
  passes ``{task_name}:{error_code}``. ``ErrorNotifier`` then applies its own
  scoping on top: without severity routing the key is used as given, and with
  routing enabled it is tier-prefixed (#286), making the effective worker key
  ``{tier}:{task_name}:{error_code}``.
- **Final-attempt gating** — ``PermanentAwareSmartRetryMiddleware`` retries
  transient failures, so dispatching on every attempt would alert up to
  ``max_retries`` times for a single incident. Permanent errors are never
  retried and alert immediately; retryable ones alert only once the last
  attempt has failed.

Ordering is a behavioural contract — see ``_install_middleware`` in
``src/_apps/worker/bootstrap.py`` and the ordering tests in
``tests/unit/_core/infrastructure/notification/``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.exceptions import NoResultError

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
)

_logger = structlog.stdlib.get_logger(__name__)


class TaskFailureNotificationMiddleware(TaskiqMiddleware):
    """Dispatch a Slack/Discord alert when a task failure is terminal."""

    def __init__(
        self,
        *,
        error_notifier_provider: Callable[[], Any],
        retry_middleware: PermanentAwareSmartRetryMiddleware,
    ) -> None:
        """
        :param error_notifier_provider: zero-arg callable returning the
            ``ErrorNotifier``. Passed as a provider rather than an instance so
            resolution stays lazy — an eager resolve at install time would
            construct ``NoopNotificationClient`` and emit
            ``notification_client_disabled`` at worker boot, diverging from the
            server's documented first-dispatch behaviour.
        :param retry_middleware: the *same instance* registered on the broker.
            Its ``is_retry_on_error`` / ``default_retry_count`` /
            ``types_of_exceptions`` decide whether a failure is terminal, so
            reading them off the live instance avoids duplicating retry
            defaults that could silently drift apart.
        """
        super().__init__()
        self._error_notifier_provider = error_notifier_provider
        self._retry_middleware = retry_middleware

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        try:
            if not self._is_terminal_failure(message, exception):
                return
            error_notifier = self._error_notifier_provider()
            error_notifier.maybe_dispatch(
                status_code=_synthetic_status_code(exception),
                error_code=_cooldown_key(message, exception),
                message=(
                    f"Task '{message.task_name}' failed: "
                    f"{type(exception).__name__}: {exception}"
                ),
            )
        except Exception:
            # Never let a notification problem become a second task failure.
            # ``exc_info`` is safe here for the same reason it is in
            # ``_dispatch_error_notification``: this block wraps only the
            # synchronous provider lookup and the non-blocking dispatch call.
            # The webhook POST fails inside ``ErrorNotifier._safe_send``, which
            # logs ``exc_type`` only so the webhook URL never reaches the log.
            _logger.warning(
                "task_error_notifier_dispatch_failed",
                taskiq_task_name=message.task_name,
                exc_info=True,
            )

    def _is_terminal_failure(
        self, message: TaskiqMessage, exception: BaseException
    ) -> bool:
        """True when no retry will follow, so this failure is the incident.

        Mirrors the decision ``PermanentAwareSmartRetryMiddleware.on_error``
        makes, reading ``_retries`` *before* that middleware increments it.
        """
        if isinstance(exception, NoResultError):
            # Signals "do not store a result", not a failure worth alerting.
            return False

        retry = self._retry_middleware

        if isinstance(exception, retry.PERMANENT_ERROR_TYPES):
            return True

        types_of_exceptions = retry.types_of_exceptions
        if types_of_exceptions is not None and not isinstance(
            exception, tuple(types_of_exceptions)
        ):
            # Outside the retry filter — the retry middleware will skip it.
            return True

        if not retry.is_retry_on_error(message):
            return True

        attempt = int(message.labels.get("_retries", 0)) + 1
        max_retries = int(message.labels.get("max_retries", retry.default_retry_count))
        return attempt >= max_retries


def _synthetic_status_code(exception: BaseException) -> int:
    """Map a task failure onto the HTTP severity scale ``ErrorNotifier`` gates on."""
    if isinstance(exception, BaseCustomException):
        return exception.status_code
    return 500


def _cooldown_key(message: TaskiqMessage, exception: BaseException) -> str:
    """Task-scoped dedupe key, so one failing task cannot mute the others."""
    error_code = getattr(exception, "error_code", None) or type(exception).__name__
    return f"{message.task_name}:{error_code}"
