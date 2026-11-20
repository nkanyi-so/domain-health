"""The store on Firestore: production, and the emulator in tests. The only module that imports
the Firestore client.

Each change is one transaction that reads every document it is about to overwrite, so of a daily
write and a click that overlap, Firestore retries whichever commits second against the new state.
What the documents hold is decided in `domain_health.store`; this module reads and writes.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

from google.api_core.exceptions import Aborted
from google.cloud.firestore import (
    AsyncClient,
    AsyncDocumentReference,
    AsyncTransaction,
    async_transactional,
)
from google.oauth2.credentials import Credentials

from domain_health.store import (
    COUNTER_LIFE,
    LIVE_WINDOW,
    ClientDay,
    ClientRecord,
    DayResult,
    HandledMark,
    LiveCheck,
    SandboxState,
    Scope,
    Slot,
    Snapshot,
    StoreBusyError,
    address_counter,
    alive,
    changed,
    checked_client_id,
    checked_domain,
    day_counter,
    found,
    sandbox_state,
    seen,
    slot,
    stored,
    with_view,
)

# What the database raises when it gives up one transaction because another holds its documents.
Busy: type[Exception] = Aborted

# How often one change is tried when the database aborts it because another writer holds the
# same documents, and the longest wait between two tries.
ATTEMPTS = 8
MAX_WAIT_SECONDS = 1.0

# Fields kept as real timestamps, because a TTL policy reads them.
_TTL_FIELD = "expires_at"


def _document(model: SandboxState | LiveCheck) -> dict[str, Any]:
    data = model.model_dump(mode="json")
    data[_TTL_FIELD] = model.expires_at
    return data


def _marks(document: dict[str, Any] | None) -> dict[str, HandledMark]:
    raw = (document or {}).get("handled") or {}
    return {risk_id: HandledMark.model_validate(mark) for risk_id, mark in raw.items()}


def _marks_field(marks: dict[str, HandledMark]) -> dict[str, Any]:
    return {risk_id: mark.model_dump(mode="json") for risk_id, mark in marks.items()}


class FirestoreStore:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db
        # Live checks in this process take their slot one at a time. Every one of them reads and
        # writes the day's counter, and ten transactions that all hold it for reading can only
        # abort each other until the retries run out. The service is one instance, so queueing
        # here removes that; the transaction is still what keeps the count right against any
        # other process.
        self._slots = asyncio.Lock()

    async def _transact[T](self, body: Callable[[AsyncTransaction], Awaitable[T]]) -> T:
        """Run one change as a transaction, again from the start if the database aborts it.

        The library retries a transaction aborted at its commit. One aborted while it reads (it
        waited too long for another writer's lock) is raised instead, and so is one that used up
        the library's own tries. Both mean "someone else was writing": the body only reads and
        then writes, so it is safe to run again against the new state.
        """
        for attempt in range(ATTEMPTS):
            try:
                return await async_transactional(body)(self.db.transaction())
            except Busy:
                pass
            except ValueError as error:
                if not isinstance(error.__cause__, Busy):
                    raise
            # Two writers that wait the same time collide again, so the wait is random.
            await asyncio.sleep(random.uniform(0, min(MAX_WAIT_SECONDS, 0.05 * 2**attempt)))  # noqa: S311
        raise StoreBusyError("the database was busy; nothing was changed")

    def _client(self, client_id: str) -> AsyncDocumentReference:
        return self.db.document("clients", checked_client_id(client_id))

    def _snapshot(self, client_id: str, day: date) -> AsyncDocumentReference:
        return self.db.document(
            "clients", checked_client_id(client_id), "snapshots", day.isoformat()
        )

    def _sandbox(self, session: str, client_id: str) -> AsyncDocumentReference:
        return self.db.document("sandboxes", session, "clients", checked_client_id(client_id))

    @staticmethod
    async def _read(
        ref: AsyncDocumentReference, transaction: AsyncTransaction | None = None
    ) -> dict[str, Any] | None:
        found = await ref.get(transaction=transaction)
        return found.to_dict() if found.exists else None

    async def _read_snapshot(
        self, client_id: str, day: date, transaction: AsyncTransaction | None = None
    ) -> Snapshot | None:
        data = await self._read(self._snapshot(client_id, day), transaction)
        return None if data is None else Snapshot.model_validate(data)

    async def _read_sandbox(
        self, session: str, client_id: str, transaction: AsyncTransaction | None = None
    ) -> SandboxState | None:
        data = await self._read(self._sandbox(session, client_id), transaction)
        return None if data is None else SandboxState.model_validate(data)

    async def write_daily(self, result: DayResult) -> Snapshot:
        client_ref = self._client(result.client_id)
        snapshot_ref = self._snapshot(result.client_id, result.day)

        async def write(transaction: AsyncTransaction) -> Snapshot:
            marks = _marks(await self._read(client_ref, transaction))
            # Read what is overwritten, so a click that lands meanwhile makes this run again.
            await self._read(snapshot_ref, transaction)
            snapshot = stored(result, marks)
            transaction.set(snapshot_ref, snapshot.model_dump(mode="json"))
            return snapshot

        return await self._transact(write)

    async def preview_daily(self, result: DayResult) -> Snapshot:
        return stored(result, _marks(await self._read(self._client(result.client_id))))

    async def mark(
        self,
        scope: Scope,
        client_id: str,
        day: date,
        risk_id: str,
        now: datetime,
        *,
        reopen: bool = False,
    ) -> ClientDay:
        client_ref = self._client(client_id)
        snapshot_ref = self._snapshot(client_id, day)
        session = scope.session

        async def click(transaction: AsyncTransaction) -> ClientDay:
            snapshot = found(await self._read_snapshot(client_id, day, transaction))
            if session is None:
                before = _marks(await self._read(client_ref, transaction))
                marks = changed(before, snapshot, risk_id, now, reopen=reopen)
                # Only the marks: the client's name and domain are not this write's.
                transaction.set(client_ref, {"handled": _marks_field(marks)}, merge=["handled"])
                transaction.set(snapshot_ref, with_view(snapshot, marks).model_dump(mode="json"))
                return seen(snapshot, marks)
            state = alive(await self._read_sandbox(session, client_id, transaction), now)
            marks = changed(state.handled if state else {}, snapshot, risk_id, now, reopen=reopen)
            if state is not None or marks:
                # A reopen by a visitor who has marked nothing makes no document.
                after = sandbox_state(marks, state, now)
                transaction.set(self._sandbox(session, client_id), _document(after))
            return seen(snapshot, marks)

        return await self._transact(click)

    async def read_day(
        self, scope: Scope, client_id: str, day: date, now: datetime
    ) -> ClientDay | None:
        snapshot = await self._read_snapshot(client_id, day)
        if snapshot is None:
            return None
        session = scope.session
        if session is None:
            return seen(snapshot, _marks(await self._read(self._client(client_id))))
        state = alive(await self._read_sandbox(session, client_id), now)
        return seen(snapshot, state.handled if state else {})

    async def take_live_check_slot(self, address_key: str, now: datetime) -> Slot:
        day_ref = self.db.document("counters", day_counter(now))
        address_ref = self.db.document("counters", address_counter(address_key, now))

        async def take(transaction: AsyncTransaction) -> Slot:
            day_count = int((await self._read(day_ref, transaction) or {}).get("count", 0))
            address_count = int((await self._read(address_ref, transaction) or {}).get("count", 0))
            given = slot(day_count, address_count)
            if given is Slot.TAKEN:
                transaction.set(day_ref, {"count": day_count + 1})
                transaction.set(
                    address_ref,
                    {"count": address_count + 1, _TTL_FIELD: now + LIVE_WINDOW + COUNTER_LIFE},
                )
            return given

        async with self._slots:
            return await self._transact(take)

    async def seed_clients(self, clients: list[ClientRecord]) -> None:
        for client in clients:
            fields = client.model_dump(mode="json", exclude={"id"})
            # Only these fields: a client's handled marks are in the same document.
            await self._client(client.id).set(fields, merge=True)

    async def list_clients(self) -> list[ClientRecord]:
        found = []
        async for document in self.db.collection("clients").stream():
            fields = document.to_dict() or {}
            if "name" not in fields:
                continue  # a document a click made before the client was seeded
            fields.pop("handled", None)
            found.append(ClientRecord(id=document.id, **fields))
        return sorted(found, key=lambda client: client.id)

    async def snapshot_documents(self, day: date) -> list[str]:
        """The path of every client's snapshot document for this day. For `make seed COUNT=`."""
        found = []
        async for client in self.db.collection("clients").list_documents():
            document = await client.collection("snapshots").document(day.isoformat()).get()
            if document.exists:
                found.append(document.reference.path)
        return sorted(found)

    async def save_live_check(self, check: LiveCheck) -> None:
        await self.db.document("live_checks", check.domain).set(_document(check))

    async def read_live_check(self, domain: str, now: datetime) -> LiveCheck | None:
        data = await self._read(self.db.document("live_checks", checked_domain(domain)))
        if data is None:
            return None
        check = LiveCheck.model_validate(data)
        return check if check.expires_at > now else None


def connect_with_token(project: str, token: str) -> FirestoreStore:
    """A store on this project's database, as whoever the short-lived access token belongs to.
    For commands run from the owner's machine; the deployed service uses `connect`."""
    return FirestoreStore(AsyncClient(project=project, credentials=Credentials(token=token)))  # type: ignore[no-untyped-call]


def connect(project: str) -> FirestoreStore:
    """A store on this project's database. With `FIRESTORE_EMULATOR_HOST` set, the client talks
    to the emulator and needs no credentials."""
    return FirestoreStore(AsyncClient(project=project))
