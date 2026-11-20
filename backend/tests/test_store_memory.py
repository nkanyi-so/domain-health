"""The memory store shows every behaviour the emulator tests ask of Firestore."""

from collections.abc import Callable, Coroutine

import pytest

from domain_health.store import SHARED, Scope, SnapshotStore
from domain_health.store.memory import MemoryStore
from tests import store_fixtures as scenarios
from tests.dns_fixtures import run

BOTH = [
    scenarios.handled_hides_and_the_next_moves_up,
    scenarios.a_rerun_keeps_the_marks,
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
