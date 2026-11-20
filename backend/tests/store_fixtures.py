"""Days to store, and the behaviours every store must show. The memory store's tests and the
emulator's run the same scenarios, so the two cannot drift apart."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from domain_health.risks import Risk, risk_id
from domain_health.seeded import checked, load_clients
from domain_health.store import (
    LIVE_PER_ADDRESS,
    LIVE_PER_DAY,
    SHARED,
    ClientRecord,
    DayResult,
    NoSnapshotError,
    Scope,
    Slot,
    SnapshotStore,
    StoreError,
    UnknownRiskError,
    live_check,
    sandbox,
)
from domain_health.types import RiskType

DAY0 = date(2026, 3, 1)
TYPES = list(RiskType)


def noon(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=UTC)


def new_client_id() -> str:
    return f"t-{uuid4().hex}"


def new_session() -> Scope:
    return sandbox(uuid4().hex)


def risks(domain: str, count: int) -> list[Risk]:
    return [
        Risk(
            id=risk_id(kind, domain),
            type=kind,
            title=f"Risk {kind.value}",
            why="Because of what the day's data shows.",
            evidence=["fixes"],
        )
        for kind in TYPES[:count]
    ]


async def day_result(
    client_id: str, day: date = DAY0, count: int = 7, *, run: int = 0
) -> DayResult:
    """A day as the worker would hand it over: real checks of a seeded client, scripted risks.
    `run` tells two runs of one day apart."""
    client = load_clients()[0]
    results, snapshot_input = await checked(client, day)
    at = noon(day) + timedelta(minutes=run)
    return DayResult(
        client_id=client_id,
        domain=client.domain,
        day=day,
        checks=results,
        sources=snapshot_input.sources,
        fixes=snapshot_input.fixes,
        risks_status="ranked",
        ranked=risks(client.domain, count),
        prompt_version="risks-v0",
        model="a-model",
        input_hash="0" * 64,
        started_at=at,
        finished_at=at,
    )


def ids(found: list[Risk]) -> list[str]:
    return [risk.id for risk in found]


async def handled_hides_and_the_next_moves_up(store: SnapshotStore, scope: Scope) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    ranked = ids(result.ranked)
    written = await store.write_daily(result)
    assert ids(written.visible) == ranked[:5]
    assert written.suppressed == []

    after = await store.mark(scope, client_id, DAY0, ranked[1], noon(DAY0))
    assert ids(after.snapshot.visible) == [ranked[0], *ranked[2:6]]
    assert ids(after.snapshot.suppressed) == [ranked[1]]
    assert after.handled[ranked[1]].until == DAY0 + timedelta(days=30)

    read = await store.read_day(scope, client_id, DAY0, noon(DAY0))
    assert read == after

    reopened = await store.mark(scope, client_id, DAY0, ranked[1], noon(DAY0), reopen=True)
    assert ids(reopened.snapshot.visible) == ranked[:5]
    assert reopened.handled == {}
    assert await store.read_day(scope, client_id, DAY0, noon(DAY0)) == reopened


async def hidden_on_day_29_and_back_on_day_30(store: SnapshotStore) -> list[str]:
    """The shared scope only: a sandbox is gone after one day. Returns one line per day checked,
    for the gate's evidence."""
    scope = SHARED
    client_id = new_client_id()
    first = await day_result(client_id)
    target = first.ranked[0].id
    await store.write_daily(first)
    await store.mark(scope, client_id, DAY0, target, noon(DAY0))
    lines = []
    for offset, expected in ((1, False), (29, False), (30, True), (31, True)):
        day = DAY0 + timedelta(days=offset)
        await store.write_daily(await day_result(client_id, day))
        seen = await store.read_day(scope, client_id, day, noon(day))
        assert seen is not None
        visible = target in ids(seen.snapshot.visible)
        assert visible is expected, f"day {offset}"
        assert (target in ids(seen.snapshot.suppressed)) is not expected, f"day {offset}"
        lines.append(f"handled on day 0, day {offset}: {'visible' if visible else 'hidden'}")
    return lines


async def a_rerun_keeps_the_marks(store: SnapshotStore, scope: Scope) -> None:
    client_id = new_client_id()
    first = await day_result(client_id)
    target = first.ranked[0].id
    await store.write_daily(first)
    await store.mark(scope, client_id, DAY0, target, noon(DAY0))

    await store.write_daily(await day_result(client_id, run=1))

    seen = await store.read_day(scope, client_id, DAY0, noon(DAY0))
    assert seen is not None
    assert target not in ids(seen.snapshot.visible)
    assert ids(seen.snapshot.suppressed) == [target]
    assert len(seen.snapshot.visible) == 5
    assert set(seen.handled) == {target}


async def a_click_on_an_older_page_hides_the_risk_on_every_day(
    store: SnapshotStore, scope: Scope
) -> None:
    """Just after midnight: today's snapshot exists and the click is made on yesterday's page."""
    client_id = new_client_id()
    yesterday, today = DAY0, DAY0 + timedelta(days=1)
    first = await day_result(client_id, yesterday)
    target = first.ranked[0].id
    await store.write_daily(first)
    await store.write_daily(await day_result(client_id, today))

    await store.mark(scope, client_id, yesterday, target, noon(today) - timedelta(hours=11))

    for day in (yesterday, today):
        seen = await store.read_day(scope, client_id, day, noon(today) - timedelta(hours=10))
        assert seen is not None
        assert target not in ids(seen.snapshot.visible), day
        assert ids(seen.snapshot.suppressed) == [target], day
        assert seen.handled[target].until == today + timedelta(days=30)


async def a_reopen_with_nothing_handled_changes_nothing(store: SnapshotStore, scope: Scope) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    await store.write_daily(result)

    after = await store.mark(scope, client_id, DAY0, result.ranked[0].id, noon(DAY0), reopen=True)

    assert after.handled == {}
    assert ids(after.snapshot.visible) == ids(result.ranked)[:5]


async def scopes_do_not_see_each_other(store: SnapshotStore) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    ranked = ids(result.ranked)
    await store.write_daily(result)
    visitor, other = new_session(), new_session()

    await store.mark(visitor, client_id, DAY0, ranked[0], noon(DAY0))

    for scope in (SHARED, other):
        seen = await store.read_day(scope, client_id, DAY0, noon(DAY0))
        assert seen is not None
        assert ids(seen.snapshot.visible) == ranked[:5]
        assert seen.handled == {}

    await store.mark(SHARED, client_id, DAY0, ranked[2], noon(DAY0))
    mine = await store.read_day(visitor, client_id, DAY0, noon(DAY0))
    assert mine is not None
    assert set(mine.handled) == {ranked[0]}
    assert ids(mine.snapshot.suppressed) == [ranked[0]]


async def a_sandbox_lives_one_day(store: SnapshotStore) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    target = result.ranked[0].id
    await store.write_daily(result)
    visitor = new_session()
    clicked = noon(DAY0)
    await store.mark(visitor, client_id, DAY0, target, clicked)

    # A later click does not extend it: both marks go a day after the first.
    second = result.ranked[1].id
    await store.mark(visitor, client_id, DAY0, second, clicked + timedelta(hours=20))
    before = await store.read_day(visitor, client_id, DAY0, clicked + timedelta(hours=23))
    assert before is not None
    assert set(before.handled) == {target, second}

    after = await store.read_day(visitor, client_id, DAY0, clicked + timedelta(hours=24))
    assert after is not None
    assert after.handled == {}
    assert target in ids(after.snapshot.visible)

    # A click after it expired starts a new sandbox, without the old marks.
    again = await store.mark(visitor, client_id, DAY0, second, clicked + timedelta(hours=25))
    assert set(again.handled) == {second}


async def a_click_needs_a_snapshot_and_a_ranked_risk(store: SnapshotStore, scope: Scope) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    try:
        await store.mark(scope, client_id, DAY0, result.ranked[0].id, noon(DAY0))
    except NoSnapshotError:
        pass
    else:
        raise AssertionError("a click with no snapshot was accepted")

    await store.write_daily(result)
    for unknown in (result.ranked[0].id + "x", f"{TYPES[-1].value}:{result.domain}", ""):
        for reopen in (False, True):
            try:
                await store.mark(scope, client_id, DAY0, unknown, noon(DAY0), reopen=reopen)
            except UnknownRiskError:
                continue
            raise AssertionError(f"a click on {unknown!r} was accepted")
    seen = await store.read_day(scope, client_id, DAY0, noon(DAY0))
    assert seen is not None
    assert seen.handled == {}


async def no_snapshot_reads_as_none(store: SnapshotStore, scope: Scope) -> None:
    assert await store.read_day(scope, new_client_id(), DAY0, noon(DAY0)) is None


async def a_live_check_is_kept_ten_minutes(store: SnapshotStore) -> None:
    result = await day_result(new_client_id())
    domain = f"{uuid4().hex}.example"
    at = noon(DAY0)
    assert await store.read_live_check(domain, at) is None
    check = live_check(domain, result.checks, result.fixes, at)
    await store.save_live_check(check)

    assert await store.read_live_check(domain, at + timedelta(minutes=9, seconds=59)) == check
    assert await store.read_live_check(domain, at + timedelta(minutes=10)) is None


async def a_preview_writes_nothing(store: SnapshotStore) -> None:
    client_id = new_client_id()
    result = await day_result(client_id)
    preview = await store.preview_daily(result)

    assert ids(preview.visible) == ids(result.ranked)[:5]
    assert await store.read_day(SHARED, client_id, DAY0, noon(DAY0)) is None


ADDRESS = "ab" * 16


async def ten_live_checks_at_once_give_at_most_five(store: SnapshotStore) -> list[Slot]:
    key = uuid4().hex
    given = await asyncio.gather(*(store.take_live_check_slot(key, noon(DAY0)) for _ in range(10)))
    assert sorted(given) == [Slot.ADDRESS_LIMIT] * 5 + [Slot.TAKEN] * 5
    # A sixth, later in the same window, is still refused; the next window is open again.
    assert (
        await store.take_live_check_slot(key, noon(DAY0) + timedelta(minutes=9))
        is Slot.ADDRESS_LIMIT
    )
    assert await store.take_live_check_slot(key, noon(DAY0) + timedelta(minutes=10)) is Slot.TAKEN
    # Another address has its own count.
    assert await store.take_live_check_slot(uuid4().hex, noon(DAY0)) is Slot.TAKEN
    return list(given)


async def the_201st_live_check_of_a_day_is_refused(store: SnapshotStore, day: date) -> None:
    """`day` must be a day no other test counts on."""
    at = noon(day)
    for _ in range(LIVE_PER_DAY // LIVE_PER_ADDRESS):
        key = uuid4().hex
        given = await asyncio.gather(
            *(store.take_live_check_slot(key, at) for _ in range(LIVE_PER_ADDRESS))
        )
        assert set(given) == {Slot.TAKEN}

    assert await store.take_live_check_slot(uuid4().hex, at) is Slot.DAILY_CAP
    assert await store.take_live_check_slot(uuid4().hex, at + timedelta(hours=11)) is Slot.DAILY_CAP
    # A refused check counts nothing, and the next UTC day starts again.
    assert await store.take_live_check_slot(uuid4().hex, at + timedelta(days=1)) is Slot.TAKEN


async def an_address_key_that_is_not_a_hash_is_refused(store: SnapshotStore) -> None:
    for key in ("", "203.0.113.7", "a/b" * 8, "AB" * 16, "g" * 32):
        try:
            await store.take_live_check_slot(key, noon(DAY0))
        except StoreError:
            continue
        raise AssertionError(f"{key!r} was used as a document name")


async def seeded_clients_are_listed_and_keep_their_marks(store: SnapshotStore) -> None:
    """Needs a store nobody else has seeded."""
    client_id = "b-client"
    result = await day_result(client_id)
    records = [
        ClientRecord(id=client_id, name="B Client", domain=result.domain),
        ClientRecord(id="a-client", name="A Client", domain="a-client.example"),
    ]
    await store.seed_clients(records)
    await store.write_daily(result)
    await store.mark(SHARED, client_id, DAY0, result.ranked[0].id, noon(DAY0))

    await store.seed_clients(records)

    assert [client.id for client in await store.list_clients()] == ["a-client", client_id]
    seen = await store.read_day(SHARED, client_id, DAY0, noon(DAY0))
    assert seen is not None
    assert set(seen.handled) == {result.ranked[0].id}
