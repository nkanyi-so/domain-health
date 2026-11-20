"""The task queue on Cloud Tasks. The only module that imports its client.

Each task is an HTTP POST to this service's own worker route, carrying an OIDC token Google
signs for the invoker service account. The queue's retry settings (five attempts, with backoff)
are set on the queue by `make infra`, not here.
"""

from datetime import UTC, date, datetime, timedelta

from google.api_core import exceptions as google_errors
from google.cloud import tasks_v2

from domain_health.tasks import QueueError


class CloudTasksQueue:
    def __init__(
        self, *, project: str, region: str, queue: str, service_url: str, invoker_email: str
    ) -> None:
        self._client = tasks_v2.CloudTasksAsyncClient()
        self._parent = self._client.queue_path(project, region, queue)
        self._service_url = service_url.rstrip("/")
        self._invoker_email = invoker_email

    async def enqueue(self, client_id: str, day: date, delay: timedelta) -> None:
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self._service_url}/internal/worker/{client_id}?day={day.isoformat()}",
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self._invoker_email, audience=self._service_url
                ),
            ),
            schedule_time=datetime.now(UTC) + delay,
        )
        try:
            await self._client.create_task(parent=self._parent, task=task)
        except google_errors.GoogleAPICallError as error:
            raise QueueError(f"Cloud Tasks refused {client_id}: {type(error).__name__}") from error
