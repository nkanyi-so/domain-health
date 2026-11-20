"""The change alert over a Slack incoming webhook. The only module that posts to one.

Never built on the hosted demo, which sets no webhook. Tests use `FakeAlerter`.
"""

import httpx2

from domain_health.alerts import AlertError

SEND_SECONDS = 5.0
# What the HTTP library raises when a send fails, named here so a test can raise it.
SEND_FAILED: type[Exception] = httpx2.HTTPError


class SlackWebhookAlerter:
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send(self, message: str) -> None:
        try:
            async with httpx2.AsyncClient(timeout=SEND_SECONDS) as client:
                response = await client.post(self._url, json={"text": message})
            response.raise_for_status()
        except SEND_FAILED as error:
            # The URL is a secret: it is never put in an error or a log line.
            raise AlertError(f"the webhook did not accept it: {type(error).__name__}") from error
