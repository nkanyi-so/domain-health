"""The Firestore store against the emulator: the same scenarios as the memory store, the race
between a click and the daily write, idempotency, the dry run and the TTL fields.

`make check` runs these inside the emulator. Every test uses names of its own, and the tests that
count documents use a database of their own (the emulator keeps one per project ID).
"""

import asyncio
import os
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from domain_health.clock import FixedClock
from domain_health.risks.model import FixtureRiskModel
from domain_health.seeded import load_clients
from domain_health.store import (
    SHARED,
    Scope,
    Slot,
    Snapshot,
    SnapshotStore,
    StoreBusyError,
    live_check,
)
from domain_health.store.firestore import FirestoreStore, connect
from domain_health.worker import ModelFacts, run_client
from tests import store_fixtures as scenarios
from tests.dns_fixtures import run
from tests.store_fixtures import DAY0, day_result, ids, new_client_id, new_session, noon
from tests.test_worker import output

pytestmark = pytest.mark.emulator

RACES = 50
FACTS = ModelFacts(prompt_version="risks-v0", model="a-model")


def store(project: str = "demo-domain-health") -> FirestoreStore:
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    assert host.startswith(("127.0.0.1:", "localhost:")), "run through `make check`"
    return connect(project)


def own_database() -> FirestoreStore:
    """An empty database nobody else writes to. A `demo-` project never reaches Google Cloud."""
    return store(f"demo-{uuid4().hex[:20]}")


async def paths(db_store: FirestoreStore) -> list[str]:
    """Every document in the database, at any depth."""
    found: list[str] = []

    async def walk(collections: object) -> None:
        async for collection in collections:  # type: ignore[attr-defined]
            async for document in collection.list_documents():
                if (await document.get()).exists:
                    found.append(document.path)
                await walk(document.collections())

    await walk(db_store.db.collections())
    return sorted(found)


BOTH = [
    scenarios.handled_hides_and_the_next_moves_up,
    scenarios.a_rerun_keeps_the_marks,
    scenarios.a_click_on_an_older_page_hides_the_risk_on_every_day,
    scenarios.a_reopen_with_nothing_handled_changes_nothing,
    scenarios.a_click_needs_a_snapshot_and_a_ranked_risk,
    scenarios.no_snapshot_reads_as_none,
]
ONCE = [
    scenarios.scopes_do_not_see_each_other,
    scenarios.a_sandbox_lives_one_day,
    scenarios.a_live_check_is_kept_ten_minutes,
    scenarios.a_preview_writes_nothing,
    scenarios.an_address_key_that_is_not_a_hash_is_refused,
]


@pytest.mark.parametrize("scenario", BOTH, ids=lambda s: s.__name__)
@pytest.mark.parametrize("shared", [True, False], ids=["shared", "sandbox"])
def test_in_both_scopes(
    scenario: Callable[[SnapshotStore, Scope], Coroutine[object, object, object]], shared: bool
) -> None:
    async def go() -> None:
        await scenario(store(), SHARED if shared else new_session())

    run(go())


@pytest.mark.parametrize("scenario", ONCE, ids=lambda s: s.__name__)
def test_scenario(scenario: Callable[[SnapshotStore], Coroutine[object, object, object]]) -> None:
    async def go() -> None:
        await scenario(store())

    run(go())


def test_handled_on_day_0_is_hidden_on_day_29_and_visible_on_day_30(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def go() -> list[str]:
        return await scenarios.hidden_on_day_29_and_back_on_day_30(store())

    lines = run(go())

    assert "handled on day 0, day 29: hidden" in lines
    assert "handled on day 0, day 30: visible" in lines
    with capsys.disabled():
        print("\n" + "\n".join(lines))


async def _race(db_store: FirestoreStore, scope: Scope) -> bool:
    """One round: a handled click and a daily write of the same day, at the same time. True when
    the click is kept and the handled risk is not visible, in the stored documents."""
    client_id = new_client_id()
    first = await day_result(client_id)
    target = first.ranked[0].id
    await db_store.write_daily(first)

    rerun = await day_result(client_id, run=1)
    await asyncio.gather(
        db_store.mark(scope, client_id, DAY0, target, noon(DAY0)),
        db_store.write_daily(rerun),
    )

    seen = await db_store.read_day(scope, client_id, DAY0, noon(DAY0))
    assert seen is not None
    # The document itself, not a view computed at the read.
    raw = await db_store.db.document("clients", client_id, "snapshots", DAY0.isoformat()).get()
    kept = Snapshot.model_validate(raw.to_dict())
    if scope.shared and (target in ids(kept.visible) or ids(kept.suppressed) != [target]):
        return False
    return (
        kept.finished_at == rerun.finished_at
        and set(seen.handled) == {target}
        and target not in ids(seen.snapshot.visible)
        and ids(seen.snapshot.suppressed) == [target]
        and len(seen.snapshot.visible) == 5
        # The daily write landed too: the stored day is the rerun's.
        and seen.snapshot.finished_at == rerun.finished_at
    )


@pytest.mark.parametrize("shared", [True, False], ids=["shared", "sandbox"])
def test_a_click_during_the_daily_write_is_kept_50_times_of_50(
    shared: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    async def go() -> int:
        db_store = store()
        # The rounds run side by side, each on a client of its own, so fifty take seconds: a
        # round's two writers wait on each other, not on the other rounds.
        rounds = [_race(db_store, SHARED if shared else new_session()) for _ in range(RACES)]
        return sum(await asyncio.gather(*rounds))

    kept = run(go())

    with capsys.disabled():
        scope = "shared" if shared else "sandbox"
        print(f"\nrace, {scope} scope: the click was kept and the risk hidden {kept} of {RACES}")
    assert kept == RACES


def test_six_clicks_at_once_on_different_risks_are_all_kept() -> None:
    """More writers than two: each waits for the others' locks, and the database aborts the ones
    that wait too long. The store runs an aborted click again, so none is lost."""

    async def go() -> None:
        db_store = store()
        for scope in (SHARED, new_session()):
            client_id = new_client_id()
            result = await day_result(client_id)
            await db_store.write_daily(result)
            wanted = ids(result.ranked)[:6]

            await asyncio.gather(
                *(db_store.mark(scope, client_id, DAY0, risk, noon(DAY0)) for risk in wanted)
            )

            seen = await db_store.read_day(scope, client_id, DAY0, noon(DAY0))
            assert seen is not None
            assert set(seen.handled) == set(wanted)
            assert ids(seen.snapshot.visible) == ids(result.ranked)[6:7]

    run(go())


def test_the_worker_run_twice_for_one_date_leaves_exactly_one_snapshot_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = load_clients()[0]
    clock = FixedClock(noon(DAY0))

    async def go() -> list[str]:
        db_store = own_database()
        for _ in range(2):
            model = FixtureRiskModel({client.domain: output(6)})
            await run_client(client, DAY0, model=model, facts=FACTS, store=db_store, clock=clock)
        return await paths(db_store)

    found = run(go())

    with capsys.disabled():
        print(f"\nworker run twice for {DAY0}: documents in the database: {found}")
    assert found == [f"clients/{client.id}/snapshots/{DAY0.isoformat()}"]


def test_a_dry_run_leaves_no_document(capsys: pytest.CaptureFixture[str]) -> None:
    client = load_clients()[0]
    clock = FixedClock(noon(DAY0))

    async def go() -> list[str]:
        db_store = own_database()
        model = FixtureRiskModel({client.domain: output(6)})
        snapshot = await run_client(
            client, DAY0, model=model, facts=FACTS, store=db_store, clock=clock, dry_run=True
        )
        assert len(snapshot.visible) == 5
        return await paths(db_store)

    found = run(go())

    with capsys.disabled():
        print(f"\ndry run: documents in the database: {len(found)}")
    assert found == []


def test_a_shared_click_leaves_the_clients_other_fields_alone() -> None:
    async def go() -> None:
        db_store = store()
        client_id = new_client_id()
        result = await day_result(client_id)
        client_ref = db_store.db.document("clients", client_id)
        await client_ref.set({"name": "A client", "domain": result.domain, "seeded": True})
        await db_store.write_daily(result)

        await db_store.mark(SHARED, client_id, DAY0, result.ranked[0].id, noon(DAY0))
        await db_store.mark(SHARED, client_id, DAY0, result.ranked[0].id, noon(DAY0), reopen=True)

        document = (await client_ref.get()).to_dict()
        assert document == {
            "name": "A client",
            "domain": result.domain,
            "seeded": True,
            "handled": {},
        }

    run(go())


def test_sandbox_and_live_check_documents_carry_a_timestamp_to_expire_by() -> None:
    async def go() -> None:
        db_store = store()
        client_id = new_client_id()
        result = await day_result(client_id)
        await db_store.write_daily(result)
        visitor = new_session()
        assert visitor.session is not None
        at = noon(DAY0)
        await db_store.mark(visitor, client_id, DAY0, result.ranked[0].id, at)

        sandbox_ref = db_store.db.document("sandboxes", visitor.session, "clients", client_id)
        expires = ((await sandbox_ref.get()).to_dict() or {})["expires_at"]
        # A TTL policy needs a timestamp, not text.
        assert isinstance(expires, datetime)
        assert expires.astimezone(UTC) == at + timedelta(days=1)

        domain = f"{uuid4().hex}.example"
        await db_store.save_live_check(live_check(domain, result.checks, result.fixes, at))
        cached = await db_store.db.document("live_checks", domain).get()
        expires = (cached.to_dict() or {})["expires_at"]
        assert isinstance(expires, datetime)
        assert expires.astimezone(UTC) == at + timedelta(minutes=10)

    run(go())


def test_a_sandbox_click_writes_nothing_shared() -> None:
    async def go() -> None:
        db_store = own_database()
        client_id = new_client_id()
        result = await day_result(client_id)
        written = await db_store.write_daily(result)
        visitor = new_session()

        await db_store.mark(visitor, client_id, DAY0, result.ranked[0].id, noon(DAY0))

        assert await paths(db_store) == sorted(
            [
                f"clients/{client_id}/snapshots/{DAY0.isoformat()}",
                f"sandboxes/{visitor.session}/clients/{client_id}",
            ]
        )
        shared = await db_store.read_day(SHARED, client_id, DAY0, noon(DAY0))
        assert shared is not None
        assert shared.snapshot == written

    run(go())


def test_reading_never_writes_whatever_day_a_visitor_reads() -> None:
    async def go() -> None:
        db_store = own_database()
        client_id = new_client_id()
        days = [DAY0, DAY0 + timedelta(days=1)]
        for day in days:
            await db_store.write_daily(await day_result(client_id, day))
        visitor = new_session()
        first = (await day_result(client_id)).ranked[0].id
        await db_store.mark(visitor, client_id, DAY0, first, noon(DAY0))

        async def everything() -> dict[str, object]:
            return {
                path: (await db_store.db.document(path).get()).to_dict()
                for path in await paths(db_store)
            }

        before = await everything()
        assert len(before) == 3
        for scope in (visitor, SHARED, new_session()):
            for day in days * 3:
                await db_store.read_day(scope, client_id, day, noon(DAY0))

        assert await everything() == before

    run(go())


def test_ten_live_checks_fired_at_once_from_one_address_give_at_most_five(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def go() -> list[Slot]:
        return await scenarios.ten_live_checks_at_once_give_at_most_five(store())

    given = run(go())

    with capsys.disabled():
        taken = sum(slot is Slot.TAKEN for slot in given)
        print(f"\nlive check: 10 fired at once from one address, {taken} succeeded")


def test_ten_live_checks_from_ten_processes_never_give_more_than_five() -> None:
    """Ten stores, as ten processes would be: nothing queues them, only the transaction counts.

    Some may be turned away busy, which the API answers with "try again"; what must never
    happen is a sixth success.
    """

    async def go() -> list[Slot | None]:
        key = uuid4().hex

        async def one() -> Slot | None:
            try:
                return await store().take_live_check_slot(key, noon(DAY0))
            except StoreBusyError:
                return None

        return list(await asyncio.gather(*(one() for _ in range(10))))

    given = run(go())

    taken = sum(slot is Slot.TAKEN for slot in given)
    assert taken <= 5
    assert all(slot in (Slot.TAKEN, Slot.ADDRESS_LIMIT, None) for slot in given)
    if None not in given:
        assert taken == 5


def test_with_the_days_counter_at_200_the_next_live_check_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def go() -> None:
        # A database of its own: the day's counter is shared by every address. The counter is
        # set, not counted up to: two hundred contending writes take the emulator minutes, and
        # the memory store's test does count them one by one through the same rule.
        db_store = own_database()
        counter = db_store.db.document("counters", f"live-{DAY0.isoformat()}")
        await counter.set({"count": 199})
        assert await db_store.take_live_check_slot("ab" * 16, noon(DAY0)) is Slot.TAKEN
        assert ((await counter.get()).to_dict() or {})["count"] == 200

        assert await db_store.take_live_check_slot("cd" * 16, noon(DAY0)) is Slot.DAILY_CAP
        assert await db_store.take_live_check_slot("ab" * 16, noon(DAY0)) is Slot.DAILY_CAP
        # A refused check counts nothing, and the next UTC day starts again.
        assert ((await counter.get()).to_dict() or {})["count"] == 200
        tomorrow = noon(DAY0) + timedelta(days=1)
        assert await db_store.take_live_check_slot("cd" * 16, tomorrow) is Slot.TAKEN

    run(go())

    with capsys.disabled():
        print("\nlive check: with the day's counter at 200, the next check was refused")


def test_a_per_address_counter_carries_a_timestamp_to_expire_by() -> None:
    async def go() -> None:
        db_store = own_database()
        await db_store.take_live_check_slot("ab" * 16, noon(DAY0))

        found = await paths(db_store)
        assert len(found) == 2
        address = next(path for path in found if path.startswith("counters/ip-"))
        fields = (await db_store.db.document(address).get()).to_dict() or {}
        assert fields["count"] == 1
        assert isinstance(fields["expires_at"], datetime)
        day = (await db_store.db.document("counters", f"live-{DAY0.isoformat()}").get()).to_dict()
        assert day == {"count": 1}

    run(go())


def test_seeded_clients_are_listed_and_keep_their_marks() -> None:
    async def go() -> None:
        await scenarios.seeded_clients_are_listed_and_keep_their_marks(own_database())

    run(go())
