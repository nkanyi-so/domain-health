"""The Cloud Tasks queue, as far as it can be tested without Cloud Tasks: how it is built."""

from domain_health.cloud_tasks import CloudTasksQueue


def test_building_the_queue_makes_no_client_and_needs_no_credentials() -> None:
    # The service builds its queue at import, outside the server's event loop. A client made
    # then is tied to the wrong loop and fails every call, which the first deploy showed.
    queue = CloudTasksQueue(
        project="demo-project",
        region="us-central1",
        queue="daily",
        service_url="https://service.example/",
        invoker_email="invoker@demo-project.example",
    )

    assert queue._client is None
    assert queue._parent == "projects/demo-project/locations/us-central1/queues/daily"
