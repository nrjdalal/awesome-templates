from src._core.infrastructure.http.http_client import HttpClient


class SlackNotificationAdapter:
    """Sends error alerts to a Slack Incoming Webhook.

    Posts directly via ``HttpClient`` instead of ``BaseHttpGateway._post``:
    a successful Slack webhook response is a plain-text ``ok`` body (not
    JSON), so parsing it as JSON would raise on every successful send.
    """

    def __init__(self, http_client: HttpClient, webhook_url: str) -> None:
        self._http_client = http_client
        self._webhook_url = webhook_url

    async def send(self, message: str) -> None:
        async with self._http_client.session() as session:
            async with session.post(
                self._webhook_url, json={"text": message}
            ) as response:
                response.raise_for_status()
