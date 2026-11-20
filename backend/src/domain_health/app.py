"""The HTTP surface: the public API behind the frontend's server routes, and the two machine
routes the schedule calls.

- `/api/*` needs the proxy secret, so the limits cannot be skipped by calling the service
  directly, and an actor: `admin` (the shared state) or `sandbox:<session>` (one visitor's own).
  Only the frontend's server can assert either, after checking its own session cookie.
- `/internal/*` needs a Google-signed token for this project's invoker (`machine_auth.py`).

Every outside system comes in through `Deps`, so tests build the app from fakes.
"""

import hashlib
import hmac
import ipaddress
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field

from domain_health.alerts import Alerter
from domain_health.check_domain import fixes_for
from domain_health.checks import CheckResults
from domain_health.checks.run import run_checks
from domain_health.clock import Clock
from domain_health.domain_name import DomainRefusedError, public_domain
from domain_health.machine_auth import KeySet, MachineRefusedError, bearer_token, verify
from domain_health.models import Fix
from domain_health.read_cache import Key, ReadCache
from domain_health.resolver import CountingResolver, Resolver
from domain_health.risks.model import RiskModel
from domain_health.seeded import SeededClient
from domain_health.store import (
    SHARED,
    ClientDay,
    HandledMark,
    NoSnapshotError,
    Scope,
    Slot,
    Snapshot,
    SnapshotStore,
    StoreBusyError,
    StoreError,
    UnknownRiskError,
    live_check,
    sandbox,
)
from domain_health.tasks import STAGGER, QueueError, TaskQueue
from domain_health.worker import ModelFacts, run_client

log = logging.getLogger(__name__)

SANDBOX_PREFIX = "sandbox:"


@dataclass(frozen=True)
class Deps:
    store: SnapshotStore
    clock: Clock
    clients: tuple[SeededClient, ...]
    model: RiskModel
    facts: ModelFacts
    queue: TaskQueue
    alerter: Alerter
    keys: KeySet
    # Builds the resolver for one live check. Called only after the name is validated and a slot
    # is taken, so nothing before that can reach real DNS.
    live_resolver: Callable[[], Resolver]
    proxy_secret: str
    service_url: str
    invoker_email: str


class Health(BaseModel):
    status: Literal["ok"]


class DaySummary(BaseModel):
    day: date
    fixes: int
    risks_visible: int
    risks_handled: int
    risks_status: Literal["ranked", "unavailable"]


class ClientSummary(BaseModel):
    id: str
    name: str
    domain: str
    seeded: bool
    # None when today has no snapshot yet.
    today: DaySummary | None


class ClientList(BaseModel):
    day: date
    clients: list[ClientSummary]


class ClientPage(BaseModel):
    id: str
    name: str
    seeded: bool
    scope: Literal["shared", "sandbox"]
    snapshot: Snapshot
    handled: dict[str, HandledMark]


class Click(BaseModel):
    day: date
    risk_id: str = Field(max_length=200)


class LiveCheckRequest(BaseModel):
    domain: str = Field(max_length=300)


class LiveCheckResult(BaseModel):
    domain: str
    checks: CheckResults
    fixes: list[Fix]
    checked_at: AwareDatetime
    # True when this is the answer kept from a check made in the last ten minutes.
    cached: bool
    queries: int | None


class Dispatched(BaseModel):
    day: date
    enqueued: list[str]
    failed: list[str]


class WorkerRun(BaseModel):
    client_id: str
    day: date
    dry_run: bool
    fixes: int
    risks_ranked: int
    risks_status: Literal["ranked", "unavailable"]
    # The document a dry run would have written. Not sent back for a real run.
    would_write: Snapshot | None = None


class NoSnapshot:
    """The cached answer "no snapshot for that day", so asking again does not read either."""


NO_SNAPSHOT = NoSnapshot()


def read_key(route: str, client_id: str | None, day: date, scope: Scope) -> Key:
    """One cached read: the route, the client, the day asked for, and whose marks it shows."""
    return (route, client_id, day, scope.session)


def counted_address(text: str) -> str:
    """The one spelling a visitor's address is counted under. `ValueError` if it is not one IP
    address and nothing else.

    A list of addresses, a port or a zone suffix is refused; an IPv4 address written inside an
    IPv6 one counts as the IPv4 address; and an IPv6 address counts as its /64, since one
    visitor usually holds a whole /64 and could otherwise be a new visitor on every call.
    """
    address = ipaddress.ip_address(text.strip())
    if isinstance(address, ipaddress.IPv4Address):
        return str(address)
    if address.scope_id is not None:
        raise ValueError("an address with a zone is not a public address")
    if address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network((address, 64), strict=False))


def address_key(address: str) -> str:
    """A visitor's address as the counters know it: a hash, so no address is ever stored."""
    return hashlib.sha256(address.encode("utf-8")).hexdigest()[:32]


def create_app(deps: Deps) -> FastAPI:
    if not deps.proxy_secret:
        # An empty secret equals an absent header, which would let every call through.
        raise ValueError("the proxy secret is empty")
    app = FastAPI(title="domain-health", docs_url=None, redoc_url=None, openapi_url=None)
    by_id = {client.id: client for client in deps.clients}
    # Belongs to this app, not the module, so two apps never share answers.
    reads: ReadCache[ClientList | ClientPage | NoSnapshot] = ReadCache()

    async def proxied(x_proxy_secret: Annotated[str | None, Header()] = None) -> None:
        given = (x_proxy_secret or "").encode("utf-8")
        if not hmac.compare_digest(given, deps.proxy_secret.encode("utf-8")):
            raise HTTPException(status_code=401, detail="not allowed")

    async def actor(x_actor: Annotated[str | None, Header()] = None) -> Scope:
        """The scope the frontend's server asserts for this request."""
        if x_actor == "admin":
            return SHARED
        if x_actor and x_actor.startswith(SANDBOX_PREFIX):
            try:
                return sandbox(x_actor.removeprefix(SANDBOX_PREFIX))
            except StoreError as error:
                raise HTTPException(status_code=400, detail="not a session") from error
        raise HTTPException(status_code=400, detail="no actor")

    async def machine(authorization: Annotated[str | None, Header()] = None) -> None:
        try:
            await verify(
                bearer_token(authorization),
                keys=deps.keys,
                audience=deps.service_url,
                invoker_email=deps.invoker_email,
            )
        except MachineRefusedError as refused:
            log.warning("a machine call was refused: %s", refused)
            raise HTTPException(status_code=401, detail="not allowed") from refused

    def seeded(client_id: str) -> SeededClient:
        if client_id not in by_id:
            raise HTTPException(status_code=404, detail="no such client")
        return by_id[client_id]

    def page(client: SeededClient, scope: Scope, seen: ClientDay) -> ClientPage:
        return ClientPage(
            id=client.id,
            name=client.name,
            seeded=True,
            scope="shared" if scope.shared else "sandbox",
            snapshot=seen.snapshot,
            handled=seen.handled,
        )

    # Not `/healthz`: Cloud Run keeps that path for itself and answers 404 before the app.
    @app.get("/health")
    async def health() -> Health:
        return Health(status="ok")

    @app.get("/api/clients", dependencies=[Depends(proxied)])
    async def clients(scope: Annotated[Scope, Depends(actor)]) -> ClientList:
        today, now = deps.clock.today(), deps.clock.now()
        key = read_key("clients", None, today, scope)
        kept = reads.get(key, now)
        if isinstance(kept, ClientList):
            return kept
        drops = reads.drops
        listed = []
        for client in deps.clients:
            seen = await deps.store.read_day(scope, client.id, today, now)
            summary = None
            if seen is not None:
                summary = DaySummary(
                    day=today,
                    fixes=len(seen.snapshot.fixes),
                    risks_visible=len(seen.snapshot.visible),
                    risks_handled=len(seen.snapshot.suppressed),
                    risks_status=seen.snapshot.risks_status,
                )
            listed.append(
                ClientSummary(
                    id=client.id, name=client.name, domain=client.domain, seeded=True, today=summary
                )
            )
        answer = ClientList(day=today, clients=listed)
        # A click or a worker run that landed during the reads may not be in this answer.
        if reads.drops == drops:
            reads.put(key, answer, now)
        return answer

    @app.get("/api/clients/{client_id}/snapshot", dependencies=[Depends(proxied)])
    async def snapshot(
        client_id: str,
        scope: Annotated[Scope, Depends(actor)],
        day: Annotated[date | None, Query()] = None,
    ) -> ClientPage:
        client = seeded(client_id)
        now = deps.clock.now()
        key = read_key("snapshot", client.id, day or deps.clock.today(), scope)
        kept = reads.get(key, now)
        if kept is None:
            drops = reads.drops
            seen = await deps.store.read_day(scope, client.id, day or deps.clock.today(), now)
            kept = NO_SNAPSHOT if seen is None else page(client, scope, seen)
            # A click or a worker run that landed during the read may not be in this answer.
            if reads.drops == drops:
                reads.put(key, kept, now)
        if not isinstance(kept, ClientPage):
            raise HTTPException(status_code=404, detail="no snapshot for that day")
        return kept

    async def click(client_id: str, scope: Scope, body: Click, *, reopen: bool) -> ClientPage:
        client = seeded(client_id)
        try:
            seen = await deps.store.mark(
                scope, client.id, body.day, body.risk_id, deps.clock.now(), reopen=reopen
            )
        except NoSnapshotError as error:
            raise HTTPException(status_code=404, detail="no snapshot for that day") from error
        except UnknownRiskError as error:
            raise HTTPException(status_code=422, detail="no such risk that day") from error
        except StoreBusyError as error:
            raise HTTPException(status_code=503, detail="busy: try again") from error
        finally:
            # Before the answer, so this caller's next page load shows the click. Also after a
            # failure: the store may have changed before it failed.
            reads.drop(lambda key: key[-1] == scope.session)
        return page(client, scope, seen)

    @app.post("/api/clients/{client_id}/handled", dependencies=[Depends(proxied)])
    async def handled(
        client_id: str, body: Click, scope: Annotated[Scope, Depends(actor)]
    ) -> ClientPage:
        return await click(client_id, scope, body, reopen=False)

    @app.post("/api/clients/{client_id}/reopen", dependencies=[Depends(proxied)])
    async def reopen(
        client_id: str, body: Click, scope: Annotated[Scope, Depends(actor)]
    ) -> ClientPage:
        return await click(client_id, scope, body, reopen=True)

    @app.post("/api/live-check", dependencies=[Depends(proxied), Depends(actor)])
    async def check_live(
        body: LiveCheckRequest,
        x_client_address: Annotated[str | None, Header()] = None,
    ) -> LiveCheckResult:
        try:
            address = counted_address(x_client_address or "")
        except ValueError as error:
            # Without an address there is nothing to limit by, so the check is not made.
            raise HTTPException(status_code=400, detail="no client address") from error
        try:
            domain = public_domain(body.domain)
        except DomainRefusedError as refused:
            raise HTTPException(
                status_code=422,
                detail={"refused": refused.reason.name.lower(), "why": str(refused)},
            ) from refused
        now = deps.clock.now()
        kept = await deps.store.read_live_check(domain, now)
        if kept is not None:
            return LiveCheckResult(
                domain=domain,
                checks=kept.checks,
                fixes=kept.fixes,
                checked_at=kept.checked_at,
                cached=True,
                queries=None,
            )
        try:
            given = await deps.store.take_live_check_slot(address_key(address), now)
        except StoreBusyError as error:
            raise HTTPException(status_code=503, detail="busy: try again") from error
        if given is not Slot.TAKEN:
            raise HTTPException(status_code=429, detail={"refused": given.value})
        # Only here, after the name, the rate limit and the daily cap, is real DNS reached.
        resolver = CountingResolver(deps.live_resolver())
        results = await run_checks(resolver, domain)
        fixes = fixes_for(results)
        await deps.store.save_live_check(live_check(domain, results, fixes, now))
        return LiveCheckResult(
            domain=domain,
            checks=results,
            fixes=fixes,
            checked_at=now,
            cached=False,
            queries=resolver.queries,
        )

    @app.post("/internal/dispatch", dependencies=[Depends(machine)])
    async def dispatch() -> Dispatched:
        """One task per client, two seconds apart. One that cannot be enqueued does not stop the
        rest; the call then fails as a whole so the schedule's own retry runs it again, which is
        safe because a rerun overwrites."""
        today = deps.clock.today()
        enqueued, failed = [], []
        for index, client in enumerate(deps.clients):
            try:
                await deps.queue.enqueue(client.id, today, STAGGER * index)
                enqueued.append(client.id)
            except QueueError as error:
                log.warning("dispatch: %s", error)
                failed.append(client.id)
        result = Dispatched(day=today, enqueued=enqueued, failed=failed)
        if failed:
            raise HTTPException(status_code=502, detail=result.model_dump(mode="json"))
        return result

    @app.post("/internal/worker/{client_id}", dependencies=[Depends(machine)])
    async def worker(
        client_id: str,
        day: Annotated[date | None, Query()] = None,
        dry_run: Annotated[bool, Query()] = False,
    ) -> WorkerRun:
        client = seeded(client_id)
        try:
            written = await run_client(
                client,
                day or deps.clock.today(),
                model=deps.model,
                facts=deps.facts,
                store=deps.store,
                clock=deps.clock,
                alerter=deps.alerter,
                dry_run=dry_run,
            )
        except StoreBusyError as error:
            # A 503 makes the queue try the task again, with its backoff.
            raise HTTPException(status_code=503, detail="busy: try again") from error
        finally:
            if not dry_run:
                # A new snapshot changes every caller's page, and must show at once.
                reads.clear()
        return WorkerRun(
            client_id=client.id,
            day=written.day,
            dry_run=dry_run,
            fixes=len(written.fixes),
            risks_ranked=len(written.ranked),
            risks_status=written.risks_status,
            would_write=written if dry_run else None,
        )

    return app
