"""The change alert: what counts as a change, and that the model's risks never do."""

import logging
from datetime import UTC, date, datetime, timedelta

import pytest

from domain_health import slack
from domain_health.alerts import AlertError, FakeAlerter, NullAlerter, changes, message
from domain_health.clock import FixedClock
from domain_health.risks.model import FixtureRiskModel
from domain_health.seeded import SeededClient, load_clients
from domain_health.slack import SlackWebhookAlerter
from domain_health.store import SHARED, DayResult, Snapshot, StoreBusyError, stored
from domain_health.store.memory import MemoryStore
from domain_health.worker import ModelFacts, run_client
from tests.dns_fixtures import run
from tests.store_fixtures import day_result
from tests.test_worker import output

FACTS = ModelFacts(prompt_version="risks-v0", model="a-model")


def a_client_whose_checks_change() -> tuple[SeededClient, date]:
    """A seeded client and a day on which its zone differs from the day before."""
    for client in load_clients():
        for offset in range(len(client.cycle)):
            day = date(2026, 3, 1) + timedelta(days=offset)
            if client.day(day).zone != client.day(day - timedelta(days=1)).zone:
                return client, day
    raise AssertionError("no seeded client changes its DNS between two days")


def run_day(
    client: SeededClient,
    day: date,
    store: MemoryStore,
    alerter: FakeAlerter,
    *,
    risks: int = 3,
    dry_run: bool = False,
) -> None:
    clock = FixedClock(datetime(day.year, day.month, day.day, 6, tzinfo=UTC))
    model = FixtureRiskModel({client.domain: output(risks)})
    run(
        run_client(
            client,
            day,
            model=model,
            facts=FACTS,
            store=store,
            clock=clock,
            alerter=alerter,
            dry_run=dry_run,
        )
    )


def test_no_yesterday_means_no_alert() -> None:
    client, day = a_client_whose_checks_change()
    alerter = FakeAlerter()

    run_day(client, day, MemoryStore(), alerter)

    assert alerter.sent == []


def test_a_check_that_differs_from_yesterdays_sends_one_message() -> None:
    client, day = a_client_whose_checks_change()
    store, alerter = MemoryStore(), FakeAlerter()
    run_day(client, day - timedelta(days=1), store, alerter)

    run_day(client, day, store, alerter)

    assert len(alerter.sent) == 1
    text = alerter.sent[0]
    assert text.startswith(f"{client.domain}: ")
    assert "since yesterday" in text
    assert "\n- " in text


def test_the_same_checks_two_days_running_send_nothing_whatever_the_model_says() -> None:
    client, day = a_client_whose_checks_change()
    store, alerter = MemoryStore(), FakeAlerter()
    run_day(client, day, store, alerter, risks=2)
    cycle = timedelta(days=len(client.cycle))

    # A whole cycle later the day's data is the same; only the model's answer differs. To make
    # that day's yesterday the same too, the store is given the same day's result as yesterday's.
    same = day + cycle
    earlier = run(store.read_day(SHARED, client.id, day, _noon(day)))
    assert earlier is not None
    store.snapshots[client.id, same - timedelta(days=1)] = earlier.snapshot
    run_day(client, same, store, alerter, risks=7)

    assert alerter.sent == []


def _noon(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=UTC)


def test_a_dry_run_sends_nothing_and_logs_what_it_would(caplog: pytest.LogCaptureFixture) -> None:
    client, day = a_client_whose_checks_change()
    store, alerter = MemoryStore(), FakeAlerter()
    run_day(client, day - timedelta(days=1), store, alerter)

    with caplog.at_level(logging.INFO):
        run_day(client, day, store, alerter, dry_run=True)

    assert alerter.sent == []
    assert "the change alert that would be sent" in caplog.text


def test_a_failed_send_is_logged_and_the_snapshot_is_still_saved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, day = a_client_whose_checks_change()
    store = MemoryStore()
    run_day(client, day - timedelta(days=1), store, FakeAlerter())

    with caplog.at_level(logging.WARNING):
        run_day(client, day, store, FakeAlerter(failing=True))

    assert (client.id, day) in store.snapshots
    assert "was not sent" in caplog.text


def test_changes_name_fields_and_fixes_in_plain_lines() -> None:
    before = run(day_result("a-client"))
    after_checks = before.checks.model_copy(update={"dmarc": before.checks.spf})
    after = before.model_copy(update={"checks": after_checks, "fixes": []})

    lines = changes(stored(before, {}), after)

    assert any(line.startswith("dmarc.") for line in lines)
    assert [line for line in lines if "fix" in line] == [
        f"fix no longer needed: {fix.type.value}"
        for fix in sorted(before.fixes, key=lambda f: f.type.value)
    ]
    assert changes(stored(before, {}), before) == []
    assert changes(None, before) == []
    assert message(after, lines).count("\n") == len(lines)


def test_a_rerun_of_a_saved_day_does_not_send_the_message_again() -> None:
    client, day = a_client_whose_checks_change()
    store, alerter = MemoryStore(), FakeAlerter()
    run_day(client, day - timedelta(days=1), store, alerter)
    run_day(client, day, store, alerter)

    run_day(client, day, store, alerter)

    assert len(alerter.sent) == 1


def test_a_run_whose_write_fails_sends_nothing() -> None:
    """The queue tries a failed run again, up to five times: the message waits for the write."""

    class BusyStore(MemoryStore):
        failing = False

        async def write_daily(self, result: DayResult) -> Snapshot:
            if self.failing:
                raise StoreBusyError("busy")
            return await super().write_daily(result)

    client, day = a_client_whose_checks_change()
    store, alerter = BusyStore(), FakeAlerter()
    run_day(client, day - timedelta(days=1), store, alerter)
    store.failing = True

    for _ in range(4):
        with pytest.raises(StoreBusyError):
            run_day(client, day, store, alerter)
    assert alerter.sent == []

    store.failing = False
    run_day(client, day, store, alerter)
    assert len(alerter.sent) == 1


def test_the_null_alerter_does_nothing() -> None:
    assert run(NullAlerter().send("anything")) is None


class _Response:
    def __init__(self, error: Exception | None) -> None:
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error


def _client(posted: list[tuple[str, object]], error: Exception | None):  # type: ignore[no-untyped-def]
    class Client:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs == {"timeout": slack.SEND_SECONDS}

        async def __aenter__(self) -> object:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, json: object) -> _Response:
            posted.append((url, json))
            return _Response(error)

    return Client


def test_the_slack_alerter_posts_the_text_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[tuple[str, object]] = []
    monkeypatch.setattr("domain_health.slack.httpx2.AsyncClient", _client(posted, None))

    run(SlackWebhookAlerter("https://hooks.example/a-secret-path").send("a change"))

    assert posted == [("https://hooks.example/a-secret-path", {"text": "a change"})]


def test_a_webhook_failure_never_shows_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    error = slack.SEND_FAILED("https://hooks.example/a-secret-path said no")
    monkeypatch.setattr("domain_health.slack.httpx2.AsyncClient", _client([], error))

    with pytest.raises(AlertError) as raised:
        run(SlackWebhookAlerter("https://hooks.example/a-secret-path").send("a change"))

    assert "a-secret-path" not in str(raised.value)
