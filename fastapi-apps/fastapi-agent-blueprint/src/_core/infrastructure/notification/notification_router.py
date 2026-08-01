from __future__ import annotations

from src._core.domain.protocols.notification_protocol import BaseNotificationProtocol


class NotificationRouter:
    """Resolves which webhook client an error notification should be sent
    to, based on a two-tier severity band (#286 — channel routing on top of
    #17's single-target ``ErrorNotifier``).

    Tiers:

    - "critical": ``status_code >= severity_threshold`` (the pre-existing
      #17 gate) → ``critical_client``.
    - "warning": ``status_code >= warning_threshold`` and
      ``< severity_threshold``, only when ``warning_threshold`` is set →
      ``warning_client``.

    When ``warning_threshold`` is ``None`` (the default), :meth:`resolve`
    only ever returns ``critical_client`` (or ``None`` below it) — matching
    #17's single-target behavior exactly, so severity routing is strictly
    opt-in and never changes what gets notified unless configured.

    ``critical_client`` and ``warning_client`` are independently resolved
    by ``CoreContainer`` from ``NOTIFICATION_CRITICAL_WEBHOOK_URL`` /
    ``NOTIFICATION_WARNING_WEBHOOK_URL``, each falling back to the shared
    single-target webhook when unset — so a partial mapping degrades to
    shared routing rather than silently dropping a tier.
    """

    def __init__(
        self,
        *,
        critical_client: BaseNotificationProtocol,
        warning_client: BaseNotificationProtocol,
        severity_threshold: int,
        warning_threshold: int | None,
    ) -> None:
        self._critical_client = critical_client
        self._warning_client = warning_client
        self._severity_threshold = severity_threshold
        self.warning_threshold = warning_threshold

    def resolve(self, status_code: int) -> BaseNotificationProtocol | None:
        """Return the client that should receive this status code, or
        ``None`` if it falls outside both configured tiers (caller should
        not dispatch)."""
        if status_code >= self._severity_threshold:
            return self._critical_client
        if self.warning_threshold is not None and status_code >= self.warning_threshold:
            return self._warning_client
        return None
