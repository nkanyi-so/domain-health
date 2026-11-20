"""`visible_risks`: thirty days of suppression, the cap of five, the next risk moving up."""

from datetime import timedelta

import pytest

from domain_health.store import (
    SUPPRESS_DAYS,
    VISIBLE_CAP,
    HandledMark,
    Scope,
    StoreError,
    changed,
    checked_client_id,
    live_check,
    sandbox,
    stored,
    visible_risks,
)
from domain_health.store.memory import MemoryStore
from tests.dns_fixtures import run
from tests.store_fixtures import DAY0, day_result, ids, noon, risks

DOMAIN = "driftwood-coffee.example"
RANKED = risks(DOMAIN, 8)


def mark(days_ago: int = 0) -> HandledMark:
    handled_on = DAY0 - timedelta(days=days_ago)
    return HandledMark(handled_at=noon(handled_on), until=handled_on + timedelta(days=30))


def test_the_numbers_are_the_specs() -> None:
    assert (SUPPRESS_DAYS, VISIBLE_CAP) == (30, 5)


def test_with_nothing_handled_the_first_five_are_visible() -> None:
    view = visible_risks(RANKED, {}, DAY0)

    assert view.visible == RANKED[:5]
    assert view.suppressed == []


def test_fewer_than_five_are_all_visible_and_none_is_none() -> None:
    assert visible_risks(RANKED[:3], {}, DAY0).visible == RANKED[:3]
    assert visible_risks([], {RANKED[0].id: mark()}, DAY0).visible == []


def test_a_handled_risk_is_hidden_and_the_sixth_moves_up() -> None:
    view = visible_risks(RANKED, {RANKED[2].id: mark()}, DAY0)

    assert view.visible == [*RANKED[:2], *RANKED[3:6]]
    assert view.suppressed == [RANKED[2]]


def test_handling_a_risk_below_the_five_changes_nothing_visible() -> None:
    view = visible_risks(RANKED, {RANKED[6].id: mark()}, DAY0)

    assert view.visible == RANKED[:5]
    assert view.suppressed == [RANKED[6]]


def test_everything_handled_leaves_nothing_visible() -> None:
    view = visible_risks(RANKED, {risk.id: mark() for risk in RANKED}, DAY0)

    assert view.visible == []
    assert view.suppressed == RANKED


def test_the_order_is_the_models_whatever_order_the_marks_were_made_in() -> None:
    handled = {RANKED[4].id: mark(1), RANKED[0].id: mark(3)}

    view = visible_risks(RANKED, handled, DAY0)

    assert view.visible == [*RANKED[1:4], *RANKED[5:7]]
    assert view.suppressed == [RANKED[0], RANKED[4]]


@pytest.mark.parametrize(("days_ago", "hidden"), [(0, True), (1, True), (29, True), (30, False)])
def test_handled_on_day_0_hidden_through_day_29_and_back_on_day_30(
    days_ago: int, hidden: bool
) -> None:
    view = visible_risks(RANKED, {RANKED[0].id: mark(days_ago)}, DAY0)

    assert (RANKED[0] in view.suppressed) is hidden
    assert (RANKED[0] not in view.visible) is hidden


def test_a_mark_on_a_risk_that_is_not_ranked_today_hides_nothing() -> None:
    view = visible_risks(RANKED[:4], {RANKED[7].id: mark()}, DAY0)

    assert view.visible == RANKED[:4]
    assert view.suppressed == []


def test_a_click_marks_for_thirty_days_from_the_utc_day_it_was_made() -> None:
    snapshot = stored(run(day_result("a-client")), {})
    target = snapshot.ranked[0].id

    marks = changed({}, snapshot, target, noon(DAY0), reopen=False)

    assert marks[target].until == DAY0 + timedelta(days=30)
    assert changed(marks, snapshot, target, noon(DAY0), reopen=True) == {}
    assert changed({}, snapshot, target, noon(DAY0), reopen=True) == {}


def test_the_daily_document_holds_the_view_the_marks_give() -> None:
    result = run(day_result("a-client"))
    snapshot = stored(result, {result.ranked[0].id: mark()})

    assert ids(snapshot.visible) == ids(result.ranked)[1:6]
    assert ids(snapshot.suppressed) == ids(result.ranked)[:1]
    assert snapshot.model_source == "recorded"


@pytest.mark.parametrize("name", ["", "a/b", "A", "a b", "-a", "a-", "..", "a.b"])
def test_a_client_id_that_could_not_be_a_document_name_is_refused(name: str) -> None:
    with pytest.raises(StoreError):
        checked_client_id(name)


@pytest.mark.parametrize("session", ["", "short", "a/b" * 8, "a" * 129, "has space " * 3])
def test_a_session_id_that_could_not_be_a_document_name_is_refused(session: str) -> None:
    with pytest.raises(StoreError):
        sandbox(session)


def test_a_scope_cannot_be_built_around_the_check() -> None:
    with pytest.raises(ValueError, match="not a session id"):
        Scope(session="a/b")


@pytest.mark.parametrize("domain", ["", "a/b.example", "A.example", "one", "a..b", "a.example/x"])
def test_a_live_check_of_a_name_that_could_not_be_a_document_name_is_refused(domain: str) -> None:
    result = run(day_result("a-client"))

    with pytest.raises(StoreError, match="not a domain name"):
        live_check(domain, result.checks, result.fixes, noon(DAY0))
    with pytest.raises(StoreError):
        run(MemoryStore().read_live_check(domain, noon(DAY0)))
