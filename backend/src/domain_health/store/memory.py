"""The store in memory, for unit tests. One lock stands in for the database's transactions."""

import asyncio
from datetime import date, datetime

from domain_health.store import (
    SHARED,
    ClientDay,
    ClientRecord,
    DayResult,
    HandledMark,
    LiveCheck,
    SandboxState,
    Scope,
    Slot,
    Snapshot,
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


class MemoryStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.snapshots: dict[tuple[str, date], Snapshot] = {}
        self.handled: dict[str, dict[str, HandledMark]] = {}
        self.sandboxes: dict[tuple[str, str], SandboxState] = {}
        self.live_checks: dict[str, LiveCheck] = {}
        self.counters: dict[str, int] = {}
        self.clients: dict[str, ClientRecord] = {}

    @property
    def documents(self) -> int:
        """How many documents the store holds, of every kind."""
        return len(self.snapshots) + len(self.handled) + len(self.sandboxes) + len(self.live_checks)

    async def write_daily(self, result: DayResult) -> Snapshot:
        checked_client_id(result.client_id)
        async with self._lock:
            snapshot = stored(result, self.handled.get(result.client_id, {}))
            self.snapshots[result.client_id, result.day] = snapshot
            return snapshot

    async def preview_daily(self, result: DayResult) -> Snapshot:
        checked_client_id(result.client_id)
        return stored(result, self.handled.get(result.client_id, {}))

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
        checked_client_id(client_id)
        async with self._lock:
            snapshot = found(self.snapshots.get((client_id, day)))
            if scope.session is None:
                before = self.handled.get(client_id, {})
                marks = changed(before, snapshot, risk_id, now, reopen=reopen)
                self.handled[client_id] = marks
                self.snapshots[client_id, day] = with_view(snapshot, marks)
                return seen(snapshot, marks)
            state = alive(self.sandboxes.get((scope.session, client_id)), now)
            marks = changed(state.handled if state else {}, snapshot, risk_id, now, reopen=reopen)
            if state is not None or marks:
                # A reopen by a visitor who has marked nothing makes no document.
                self.sandboxes[scope.session, client_id] = sandbox_state(marks, state, now)
            return seen(snapshot, marks)

    async def read_day(
        self, scope: Scope, client_id: str, day: date, now: datetime
    ) -> ClientDay | None:
        checked_client_id(client_id)
        snapshot = self.snapshots.get((client_id, day))
        if snapshot is None:
            return None
        if scope.session is None:
            return seen(snapshot, self.handled.get(client_id, {}))
        state = alive(self.sandboxes.get((scope.session, client_id)), now)
        return seen(snapshot, state.handled if state else {})

    async def take_live_check_slot(self, address_key: str, now: datetime) -> Slot:
        day, address = day_counter(now), address_counter(address_key, now)
        async with self._lock:
            given = slot(self.counters.get(day, 0), self.counters.get(address, 0))
            if given is Slot.TAKEN:
                self.counters[day] = self.counters.get(day, 0) + 1
                self.counters[address] = self.counters.get(address, 0) + 1
            return given

    async def seed_clients(self, clients: list[ClientRecord]) -> None:
        for client in clients:
            self.clients[client.id] = client

    async def list_clients(self) -> list[ClientRecord]:
        return [self.clients[client_id] for client_id in sorted(self.clients)]

    async def save_live_check(self, check: LiveCheck) -> None:
        self.live_checks[check.domain] = check

    async def read_live_check(self, domain: str, now: datetime) -> LiveCheck | None:
        check = self.live_checks.get(checked_domain(domain))
        return check if check is not None and check.expires_at > now else None


__all__ = ["SHARED", "MemoryStore"]
