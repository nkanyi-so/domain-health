"""The short cache on the two public read routes: a repeated page load costs no store read, and
nobody is shown a page older than their own click or the last worker run."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from domain_health.app import create_app
from domain_health.clock import FixedClock
from domain_health.models import SnapshotInput
from domain_health.read_cache import MAX_ENTRIES, TIME_TO_LIVE, Key, ReadCache
from domain_health.risks import Risk
from domain_health.risks.model import FixtureRiskModel
from domain_health.store import ClientDay, Scope, StoreError
from domain_health.store.memory import MemoryStore
from tests.app_fixtures import ADMIN, NOW, PROXY_SECRET, VISITOR, build, machine
from tests.test_worker import output

CLIENT = "brindle-and-oak"
DAY = NOW.date().isoformat()
LIST = "/api/clients"
PAGE = f"/api/clients/{CLIENT}/snapshot"
WORKER = f"/internal/worker/{CLIENT}"
OTHER = {"X-Proxy-Secret": PROXY_SECRET, "X-Actor": f"sandbox:{'b' * 32}"}
JUST_UNDER = TIME_TO_LIVE - timedelta(microseconds=1)


class CountingStore(MemoryStore):
    """Counts the reads the public routes make, and can be told to fail them."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0
        self.failing = False
        # Set by a test to hold one read after it has seen the store, until the test lets it go.
        self.held: threading.Event | None = None
        self.holding = threading.Event()

    async def read_day(
        self, scope: Scope, client_id: str, day: date, now: datetime
    ) -> ClientDay | None:
        self.reads += 1
        if self.failing:
            raise StoreError("the store is away")
        seen = await super().read_day(scope, client_id, day, now)
        if self.held is not None:
            held, self.held = self.held, None
            self.holding.set()
            # In a thread, so the loop serving the other request is not blocked.
            await asyncio.to_thread(held.wait)
        return seen


class ChangingModel:
    """Answers with as many risks as the test last asked for, so a rerun can differ."""

    def __init__(self) -> None:
        self.count = 0

    async def rank(self, snapshot: SnapshotInput) -> list[Risk]:
        return await FixtureRiskModel({snapshot.domain: output(self.count)}).rank(snapshot)


class Service:
    """One app over a counting store, with a clock the test moves."""

    def __init__(self, count: int | None = 7) -> None:
        self.store = CountingStore()
        self.clock = FixedClock(NOW)
        self.model = ChangingModel()
        deps = replace(build(store=self.store).deps, clock=self.clock, model=self.model)
        self.client = TestClient(create_app(deps), raise_server_exceptions=False)
        if count is not None:
            self.run_worker(count)

    def run_worker(self, count: int) -> None:
        self.model.count = count
        assert self.client.post(WORKER, headers=machine()).status_code == 200

    def wait(self, time: timedelta) -> None:
        self.clock.at += time

    def reads_for(self, path: str, headers: dict[str, str]) -> int:
        """How many store reads one GET made. The GET must answer 200."""
        before = self.store.reads
        assert self.client.get(path, headers=headers).status_code == 200
        return self.store.reads - before

    def visible(self, headers: dict[str, str]) -> list[str]:
        page = self.client.get(PAGE, headers=headers).json()
        return [item["id"] for item in page["snapshot"]["visible"]]

    def click(self, action: str, risk_id: str, headers: dict[str, str]) -> None:
        body = {"day": DAY, "risk_id": risk_id}
        clicked = self.client.post(f"/api/clients/{CLIENT}/{action}", json=body, headers=headers)
        assert clicked.status_code == 200


def handled_in_list(service: Service, headers: dict[str, str]) -> int:
    """How many risks the client list says this caller has handled for the client today."""
    listed = service.client.get(LIST, headers=headers).json()
    today: dict[str, int] = next(c for c in listed["clients"] if c["id"] == CLIENT)["today"]
    return today["risks_handled"]


def key(name: str, session: str | None = None) -> Key:
    return (name, session)


def test_an_entry_is_kept_until_exactly_the_time_to_live() -> None:
    cache: ReadCache[str] = ReadCache()
    cache.put(key("a"), "kept", NOW)

    assert cache.get(key("a"), NOW) == "kept"
    assert cache.get(key("a"), NOW + JUST_UNDER) == "kept"
    assert cache.get(key("a"), NOW + TIME_TO_LIVE) is None
    # Once too old it is gone, even for a clock that goes back.
    assert cache.get(key("a"), NOW) is None
    assert len(cache) == 0


def test_the_time_to_live_is_thirty_seconds_and_nothing_else_is_ever_found() -> None:
    cache: ReadCache[str] = ReadCache()

    assert timedelta(seconds=30) == TIME_TO_LIVE
    assert cache.get(key("never put"), NOW) is None


def test_an_entry_put_in_the_future_is_not_trusted() -> None:
    cache: ReadCache[str] = ReadCache()
    cache.put(key("a"), "kept", NOW)

    assert cache.get(key("a"), NOW - timedelta(seconds=1)) is None


def test_a_second_put_replaces_the_answer_and_starts_its_time_again() -> None:
    cache: ReadCache[str] = ReadCache()
    cache.put(key("a"), "old", NOW)
    cache.put(key("a"), "new", NOW + timedelta(seconds=20))

    assert cache.get(key("a"), NOW + timedelta(seconds=40)) == "new"
    assert len(cache) == 1


def test_a_full_cache_drops_the_oldest_first() -> None:
    cache: ReadCache[int] = ReadCache(max_entries=3)
    for number in range(3):
        cache.put(key(str(number)), number, NOW)
    # Put again, so "0" is now the newest and "1" the oldest.
    cache.put(key("0"), 0, NOW)

    cache.put(key("3"), 3, NOW)

    assert len(cache) == 3
    assert cache.get(key("1"), NOW) is None
    assert [cache.get(key(name), NOW) for name in ("0", "2", "3")] == [0, 2, 3]


def test_the_cache_never_holds_more_than_its_bound() -> None:
    cache: ReadCache[int] = ReadCache()
    for number in range(MAX_ENTRIES + 50):
        cache.put(key(str(number)), number, NOW)

    assert len(cache) == MAX_ENTRIES
    assert 100 <= MAX_ENTRIES <= 1000
    assert cache.get(key("49"), NOW) is None
    assert cache.get(key("50"), NOW) == 50


def test_drop_forgets_one_scope_and_leaves_the_rest() -> None:
    cache: ReadCache[str] = ReadCache()
    cache.put(key("list", "mine"), "a", NOW)
    cache.put(key("page", "mine"), "b", NOW)
    cache.put(key("page", "theirs"), "c", NOW)
    cache.put(key("page", None), "d", NOW)

    cache.drop(lambda kept: kept[-1] == "mine")

    assert cache.get(key("list", "mine"), NOW) is None
    assert cache.get(key("page", "mine"), NOW) is None
    assert cache.get(key("page", "theirs"), NOW) == "c"
    assert cache.get(key("page", None), NOW) == "d"


def test_clear_forgets_everything_and_both_ways_of_forgetting_are_counted() -> None:
    cache: ReadCache[str] = ReadCache()
    cache.put(key("a"), "a", NOW)
    cache.put(key("b", "mine"), "b", NOW)
    assert cache.drops == 0

    cache.drop(lambda kept: False)
    assert (len(cache), cache.drops) == (2, 1)
    cache.clear()

    assert (len(cache), cache.drops) == (0, 2)


def test_a_second_client_list_within_thirty_seconds_reads_nothing() -> None:
    service = Service()

    assert service.reads_for(LIST, VISITOR) == 12
    first = service.client.get(LIST, headers=VISITOR).json()
    service.wait(JUST_UNDER)
    assert service.reads_for(LIST, VISITOR) == 0
    assert service.client.get(LIST, headers=VISITOR).json() == first

    service.wait(timedelta(microseconds=1))
    assert service.reads_for(LIST, VISITOR) == 12


def test_a_second_snapshot_within_thirty_seconds_reads_nothing() -> None:
    service = Service()

    assert service.reads_for(PAGE, VISITOR) == 1
    first = service.client.get(PAGE, headers=VISITOR).json()
    service.wait(JUST_UNDER)
    # Today asked for by name is the same page.
    assert service.reads_for(f"{PAGE}?day={DAY}", VISITOR) == 0
    assert service.client.get(PAGE, headers=VISITOR).json() == first

    service.wait(timedelta(microseconds=1))
    assert service.reads_for(PAGE, VISITOR) == 1


def test_no_snapshot_for_that_day_is_cached_too() -> None:
    service = Service()
    path = f"{PAGE}?day=2026-02-01"
    before = service.store.reads

    answers = [service.client.get(path, headers=VISITOR) for _ in range(5)]

    assert [answer.status_code for answer in answers] == [404] * 5
    assert answers[-1].json() == {"detail": "no snapshot for that day"}
    # Only the first of the five read the store.
    assert service.store.reads == before + 1
    service.wait(TIME_TO_LIVE)
    assert service.client.get(path, headers=VISITOR).status_code == 404
    assert service.store.reads == before + 2


def test_each_day_and_each_client_is_its_own_entry() -> None:
    service = Service()
    before = service.store.reads
    service.client.get(PAGE, headers=VISITOR)

    assert service.client.get(f"{PAGE}?day=2026-02-01", headers=VISITOR).status_code == 404
    other_client = service.client.get("/api/clients/copperkettle-kitchen/snapshot", headers=VISITOR)

    assert other_client.status_code == 404
    assert service.store.reads == before + 3
    assert service.reads_for(PAGE, VISITOR) == 0


def test_a_visitors_click_shows_on_their_very_next_read() -> None:
    service = Service()
    first = service.visible(VISITOR)[0]
    assert handled_in_list(service, VISITOR) == 0

    service.click("handled", first, VISITOR)

    assert first not in service.visible(VISITOR)
    page = service.client.get(PAGE, headers=VISITOR).json()
    assert list(page["handled"]) == [first]
    # The list was dropped with the page: it is read again, not answered from before the click.
    assert service.reads_for(LIST, VISITOR) == 12
    assert handled_in_list(service, VISITOR) == 1

    service.click("reopen", first, VISITOR)

    assert service.visible(VISITOR)[0] == first


def test_a_visitors_click_does_not_drop_another_callers_cached_page() -> None:
    service = Service()
    first = service.visible(VISITOR)[0]
    for headers in (OTHER, ADMIN):
        service.client.get(PAGE, headers=headers)
        service.client.get(LIST, headers=headers)

    service.click("handled", first, VISITOR)

    for headers in (OTHER, ADMIN):
        assert service.reads_for(PAGE, headers) == 0
        assert service.reads_for(LIST, headers) == 0
        assert service.visible(headers)[0] == first


def test_an_admins_click_shows_on_the_admins_next_read() -> None:
    service = Service()
    first = service.visible(ADMIN)[0]
    assert handled_in_list(service, ADMIN) == 0
    service.client.get(PAGE, headers=VISITOR)

    service.click("handled", first, ADMIN)

    page = service.client.get(PAGE, headers=ADMIN).json()
    assert [item["id"] for item in page["snapshot"]["suppressed"]] == [first]
    assert list(page["handled"]) == [first]
    assert handled_in_list(service, ADMIN) == 1
    # A visitor's page shows their own marks, so the admin's click did not make it stale.
    assert service.reads_for(PAGE, VISITOR) == 0

    service.click("reopen", first, ADMIN)

    assert service.visible(ADMIN)[0] == first


def test_a_read_that_a_click_overtook_is_not_kept() -> None:
    service = Service()
    first = service.visible(VISITOR)[0]
    service.click("reopen", first, VISITOR)
    release = service.store.held = threading.Event()

    with ThreadPoolExecutor(max_workers=1) as pool:
        slow = pool.submit(service.visible, VISITOR)
        assert service.store.holding.wait(timeout=5)
        # The slow read has seen the store; the click lands and answers before it returns.
        service.click("handled", first, VISITOR)
        release.set()
        stale = slow.result(timeout=5)

    assert first in stale
    assert first not in service.visible(VISITOR)


def test_a_read_that_a_worker_run_overtook_is_not_kept() -> None:
    service = Service(count=None)
    release = service.store.held = threading.Event()

    with ThreadPoolExecutor(max_workers=1) as pool:
        slow = pool.submit(service.client.get, PAGE, headers=VISITOR)
        assert service.store.holding.wait(timeout=5)
        service.run_worker(7)
        release.set()
        assert slow.result(timeout=5).status_code == 404

    assert len(service.visible(VISITOR)) == 5


def test_a_click_that_is_refused_still_leaves_the_next_read_fresh() -> None:
    service = Service()
    service.client.get(PAGE, headers=VISITOR)
    body = {"day": DAY, "risk_id": "no-such-risk"}

    refused = service.client.post(f"/api/clients/{CLIENT}/handled", json=body, headers=VISITOR)

    assert refused.status_code == 422
    assert service.reads_for(PAGE, VISITOR) == 1


def test_a_worker_run_shows_on_the_next_read_at_once() -> None:
    service = Service(count=None)
    assert service.client.get(PAGE, headers=VISITOR).status_code == 404
    listed = service.client.get(LIST, headers=ADMIN).json()
    assert all(client["today"] is None for client in listed["clients"])

    service.run_worker(7)

    assert len(service.visible(VISITOR)) == 5
    listed = service.client.get(LIST, headers=ADMIN).json()
    assert next(c for c in listed["clients"] if c["id"] == CLIENT)["today"] is not None

    # A rerun that ranks fewer risks shows at once too.
    service.run_worker(2)

    assert len(service.visible(VISITOR)) == 2
    assert len(service.visible(ADMIN)) == 2


def test_a_dry_run_writes_nothing_and_drops_nothing() -> None:
    service = Service()
    service.client.get(PAGE, headers=VISITOR)

    dry = service.client.post(f"{WORKER}?dry_run=true", headers=machine())

    assert dry.status_code == 200
    assert service.reads_for(PAGE, VISITOR) == 0


def test_two_sandbox_sessions_never_see_each_others_cached_page() -> None:
    service = Service()
    first = service.visible(VISITOR)[0]
    service.click("handled", first, VISITOR)
    mine = service.client.get(PAGE, headers=VISITOR).json()
    my_list = service.client.get(LIST, headers=VISITOR).json()

    theirs = service.client.get(PAGE, headers=OTHER).json()

    assert list(mine["handled"]) == [first]
    assert theirs["handled"] == {}
    assert theirs["snapshot"]["visible"][0]["id"] == first
    # Each session's first read went to the store, and neither was answered from the other's.
    assert service.reads_for(LIST, OTHER) == 12
    assert service.reads_for(PAGE, OTHER) == 0
    assert service.client.get(PAGE, headers=VISITOR).json() == mine
    assert service.client.get(LIST, headers=VISITOR).json() == my_list
    assert service.client.get(PAGE, headers=ADMIN).json()["scope"] == "shared"


def test_a_store_error_is_not_cached() -> None:
    service = Service()
    service.store.failing = True

    assert service.client.get(PAGE, headers=VISITOR).status_code == 500
    assert service.client.get(LIST, headers=VISITOR).status_code == 500
    service.store.failing = False

    assert service.reads_for(PAGE, VISITOR) == 1
    assert service.reads_for(LIST, VISITOR) == 12
    assert len(service.visible(VISITOR)) == 5


def test_two_apps_do_not_share_a_cache() -> None:
    first, second = Service(), Service(count=None)

    assert first.client.get(PAGE, headers=VISITOR).status_code == 200
    assert second.client.get(PAGE, headers=VISITOR).status_code == 404
    assert second.store.reads == 1
