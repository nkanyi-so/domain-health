"""`/internal/*`: who may call it, what dispatch enqueues, what the worker does.

The six auth cases are the ones the original system never exercised before its first scheduled
run: here they run in CI, with tokens signed by a local key against a fake key set.
"""

from datetime import timedelta

import pytest

from domain_health.alerts import FakeAlerter
from domain_health.store import SHARED
from domain_health.store.memory import MemoryStore
from domain_health.tasks import FakeQueue
from tests.app_fixtures import INVOKER, NOW, SERVICE_URL, build, certificate, machine, token
from tests.dns_fixtures import run
from tests.test_worker import output

CLIENT = "brindle-and-oak"
WORKER = f"/internal/worker/{CLIENT}"

REFUSED = {
    "a wrong audience": machine(audience="https://another-service.example"),
    "a wrong service account": machine(email="someone-else@a-project.iam.gserviceaccount.com"),
    "an expired token": machine(expires_in=timedelta(minutes=-5)),
    "a bad signature": machine(signed_by="an-attacker"),
}


def test_a_valid_token_gets_200() -> None:
    for path in (WORKER, "/internal/dispatch"):
        assert build().client.post(path, headers=machine()).status_code == 200, path


def test_a_missing_token_gets_401() -> None:
    for path in (WORKER, "/internal/dispatch"):
        for headers in ({}, {"Authorization": ""}, {"Authorization": "Bearer "}):
            assert build().client.post(path, headers=headers).status_code == 401, path


@pytest.mark.parametrize("case", list(REFUSED))
def test_each_wrong_token_gets_401_and_does_nothing(case: str) -> None:
    queue = FakeQueue()
    built = build(queue=queue)

    for path in (WORKER, "/internal/dispatch"):
        response = built.client.post(path, headers=REFUSED[case])
        assert response.status_code == 401, path
        # The reason is logged, never sent back.
        assert response.json() == {"detail": "not allowed"}

    assert queue.tasks == []
    assert isinstance(built.store, MemoryStore)
    assert built.store.documents == 0


@pytest.mark.parametrize(
    "headers",
    [
        machine(issuer="https://accounts.example"),
        machine(email_verified=False),
        machine(key_id="a-key-google-does-not-have"),
        {"Authorization": f"Basic {token()}"},
        {"Authorization": f"Bearer {token()}x"},
        {"Authorization": "Bearer not.a.token"},
        {"Authorization": f"Bearer {token().rsplit('.', 1)[0]}."},
        # The frontend's credentials are not a machine's.
        {"X-Proxy-Secret": "a-proxy-secret-for-tests", "X-Actor": "admin"},
    ],
    ids=[
        "another issuer",
        "email not verified",
        "unknown key",
        "not bearer",
        "tampered",
        "not a token",
        "no signature",
        "the proxy secret",
    ],
)
def test_other_wrong_callers_get_401(headers: dict[str, str]) -> None:
    assert build().client.post(WORKER, headers=headers).status_code == 401


def test_an_unsigned_token_naming_no_algorithm_is_refused() -> None:
    import base64
    import json

    def part(value: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    claims = {
        "iss": "https://accounts.google.com",
        "aud": SERVICE_URL,
        "email": INVOKER,
        "email_verified": True,
        "exp": 9999999999,
        "iat": 0,
    }
    forged = f"{part({'alg': 'none'})}.{part(claims)}."
    headers = {"Authorization": f"Bearer {forged}"}

    assert build().client.post(WORKER, headers=headers).status_code == 401


def test_a_token_that_names_no_key_is_checked_against_every_key() -> None:
    client = build().client

    assert client.post(WORKER, headers=machine(key_id=None)).status_code == 200
    headers = machine(key_id=None, signed_by="an-attacker")
    assert client.post(WORKER, headers=headers).status_code == 401


def test_the_certificate_fixture_is_a_certificate() -> None:
    assert certificate().startswith("-----BEGIN CERTIFICATE-----")
    assert certificate() != certificate("an-attacker")


def test_dispatch_enqueues_one_task_per_client_two_seconds_apart() -> None:
    queue = FakeQueue()
    built = build(queue=queue)

    response = built.client.post("/internal/dispatch", headers=machine())

    assert response.status_code == 200
    ids = [client.id for client in built.deps.clients]
    assert response.json() == {"day": "2026-03-01", "enqueued": ids, "failed": []}
    assert [task.client_id for task in queue.tasks] == ids
    assert len(ids) == 12
    assert [task.delay for task in queue.tasks] == [timedelta(seconds=2 * n) for n in range(12)]
    assert {task.day for task in queue.tasks} == {NOW.date()}


def test_one_client_that_cannot_be_enqueued_does_not_block_the_rest() -> None:
    queue = FakeQueue(failing=frozenset({"copperkettle-kitchen"}))
    built = build(queue=queue)

    response = built.client.post("/internal/dispatch", headers=machine())

    # The whole call fails so that the schedule runs it again; the other eleven are enqueued.
    assert response.status_code == 502
    assert response.json()["detail"]["failed"] == ["copperkettle-kitchen"]
    assert len(queue.tasks) == 11


def test_the_worker_writes_the_days_snapshot_and_twice_leaves_one() -> None:
    domain = f"{CLIENT}.example"
    built = build(outputs={domain: output(6)})

    for _ in range(2):
        response = built.client.post(WORKER, headers=machine())
        assert response.status_code == 200
        assert response.json() == {
            "client_id": CLIENT,
            "day": "2026-03-01",
            "dry_run": False,
            "fixes": response.json()["fixes"],
            "risks_ranked": 6,
            "risks_status": "ranked",
            "would_write": None,
        }

    assert isinstance(built.store, MemoryStore)
    assert list(built.store.snapshots) == [(CLIENT, NOW.date())]
    assert built.store.documents == 1


def test_the_worker_runs_the_day_the_task_names() -> None:
    built = build()

    response = built.client.post(f"{WORKER}?day=2026-02-27", headers=machine())

    assert response.json()["day"] == "2026-02-27"
    assert run(built.store.read_day(SHARED, CLIENT, NOW.date(), NOW)) is None


def test_a_dry_run_returns_the_document_and_writes_nothing() -> None:
    built = build(outputs={f"{CLIENT}.example": output(6)})

    response = built.client.post(f"{WORKER}?dry_run=true", headers=machine())

    body = response.json()
    assert response.status_code == 200
    assert body["dry_run"] is True
    assert body["would_write"]["client_id"] == CLIENT
    assert len(body["would_write"]["visible"]) == 5
    assert isinstance(built.store, MemoryStore)
    assert built.store.documents == 0


def test_a_model_that_gives_nothing_still_gets_200_with_risks_unavailable() -> None:
    response = build().client.post(WORKER, headers=machine())

    assert response.status_code == 200
    assert response.json()["risks_status"] == "unavailable"


def test_the_worker_refuses_a_client_that_is_not_seeded_and_a_bad_day() -> None:
    client = build().client

    assert client.post("/internal/worker/nobody", headers=machine()).status_code == 404
    assert client.post(f"{WORKER}?day=tomorrow", headers=machine()).status_code == 422


def test_a_get_on_a_machine_route_is_not_allowed() -> None:
    client = build().client

    assert client.get(WORKER, headers=machine()).status_code == 405
    assert client.get("/internal/dispatch", headers=machine()).status_code == 405


def test_the_worker_passes_the_alerter_on() -> None:
    alerter = FakeAlerter()
    built = build(alerter=alerter)

    built.client.post(f"{WORKER}?day=2026-02-28", headers=machine())
    built.client.post(WORKER, headers=machine())

    # Two consecutive days of this client differ in the fixtures or they do not: either way the
    # alerter is the one the app was given, and nothing is sent without a yesterday.
    assert all(text.startswith(f"{CLIENT}.example: ") for text in alerter.sent)
