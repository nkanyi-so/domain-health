"""The Firestore store's own retry: a change the database aborts is run again, a bounded number
of times, and anything else is not swallowed. No database: the transaction runner is a fake."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from domain_health.store import StoreBusyError
from domain_health.store import firestore as module
from domain_health.store.firestore import ATTEMPTS, FirestoreStore
from tests.dns_fixtures import run


class FakeDb:
    def transaction(self) -> object:
        return object()


def store_failing_with(
    monkeypatch: pytest.MonkeyPatch, failures: list[Exception]
) -> tuple[FirestoreStore, list[int]]:
    """A store whose next transactions fail with these errors, in order, then succeed."""
    calls: list[int] = []

    def runner(body: Callable[[Any], Awaitable[Any]]) -> Callable[[Any], Awaitable[Any]]:
        async def run_once(transaction: Any) -> Any:
            calls.append(1)
            if len(calls) <= len(failures):
                raise failures[len(calls) - 1]
            return await body(transaction)

        return run_once

    async def no_wait(seconds: float) -> None:
        assert 0 <= seconds <= module.MAX_WAIT_SECONDS

    monkeypatch.setattr(module, "async_transactional", runner)
    monkeypatch.setattr("domain_health.store.firestore.asyncio.sleep", no_wait)
    return FirestoreStore(FakeDb()), calls  # type: ignore[arg-type]


async def body(transaction: object) -> str:
    return "done"


def exhausted() -> ValueError:
    """What the library raises when its own tries at the commit are used up."""
    error = ValueError("Failed to commit transaction in 5 attempts.")
    error.__cause__ = module.Busy("lock timeout")
    return error


def test_a_change_aborted_while_reading_or_at_commit_is_run_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, calls = store_failing_with(monkeypatch, [module.Busy("lock timeout"), exhausted()])

    assert run(store._transact(body)) == "done"
    assert len(calls) == 3


def test_a_database_that_stays_busy_is_reported_and_not_tried_for_ever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, calls = store_failing_with(monkeypatch, [module.Busy("busy")] * 100)

    with pytest.raises(StoreBusyError):
        run(store._transact(body))
    assert len(calls) == ATTEMPTS


@pytest.mark.parametrize("error", [ValueError("something else"), RuntimeError("broken")])
def test_any_other_failure_is_raised_at_once(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    store, calls = store_failing_with(monkeypatch, [error])

    with pytest.raises(type(error)):
        run(store._transact(body))
    assert len(calls) == 1
