"""The memory store shows every behaviour the emulator tests ask of Firestore."""

from collections.abc import Callable, Coroutine
from datetime import timedelta

import pytest

from domain_health.store import SHARED, Scope, SnapshotStore
from domain_health.store.memory import MemoryStore
from tests import store_fixtures as scenarios
from tests.dns_fixtures import run

BOTH = [
    scenarios.handled_hides_and_the_next_moves_up,
    scenarios.a_rerun_keeps_the_marks,
    scenarios.a_click_on_an_older_page_hides_the_risk_on_every_day,
    scenarios.a_reopen_with_nothing_handled_changes_nothing,
    scenarios.a_click_needs_a_snapshot_and_a_ranked_risk,
    scenarios.no_snapshot_reads_as_none,
]
ONCE = [
    scenarios.hidden_on_day_29_and_back_on_day_30,
    scenarios.scopes_do_not_see_each_other,
    scenarios.a_sandbox_lives_one_day,
    scenarios.a_live_check_is_kept_ten_minutes,
    scenarios.a_preview_writes_nothing,
]


@pytest.mark.parametrize("scenario", BOTH, ids=lambda s: s.__name__)
@pytest.mark.parametrize("shared", [True, False], ids=["shared", "sandbox"])
def test_in_both_scopes(
    scenario: Callable[[SnapshotStore, Scope], Coroutine[object, object, object]], shared: bool
) -> None:
    run(scenario(MemoryStore(), SHARED if shared else scenarios.new_session()))


@pytest.mark.parametrize("scenario", ONCE, ids=lambda s: s.__name__)
def test_scenario(scenario: Callable[[SnapshotStore], Coroutine[object, object, object]]) -> None:
    run(scenario(MemoryStore()))


def test_a_preview_leaves_no_document() -> None:
    store = MemoryStore()
    run(store.preview_daily(run(scenarios.day_result("a-client"))))

    assert store.documents == 0


def test_reading_never_writes_whatever_day_a_visitor_reads() -> None:
    async def go() -> None:
        store = MemoryStore()
        client_id = scenarios.new_client_id()
        days = [scenarios.DAY0, scenarios.DAY0 + timedelta(days=1)]
        for day in days:
            await store.write_daily(await scenarios.day_result(client_id, day))
        visitor = scenarios.new_session()
        first = (await scenarios.day_result(client_id)).ranked[0].id
        at = scenarios.noon(scenarios.DAY0)
        await store.mark(visitor, client_id, days[0], first, at)
        before = (dict(store.snapshots), dict(store.handled), dict(store.sandboxes))

        for scope in (visitor, SHARED, scenarios.new_session()):
            for day in days * 3:
                await store.read_day(scope, client_id, day, at)

        assert (store.snapshots, store.handled, store.sandboxes) == before

    run(go())
