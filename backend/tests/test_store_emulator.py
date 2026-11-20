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
from domain_health.store import SHARED, Scope, SnapshotStore, live_check
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
    scenarios.a_click_needs_a_snapshot_and_a_ranked_risk,
    scenarios.no_snapshot_reads_as_none,
]
ONCE = [
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
    return (
        set(seen.handled) == {target}
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
