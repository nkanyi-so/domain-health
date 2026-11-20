"""The store in memory, for unit tests. One lock stands in for the database's transactions."""

import asyncio
from datetime import date, datetime

from domain_health.store import (
    SHARED,
    ClientDay,
    DayResult,
    HandledMark,
    LiveCheck,
    SandboxState,
    Scope,
    Snapshot,
    alive,
    changed,
    checked_client_id,
    found,
    sandbox_day,
    sandbox_state,
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
                seen = with_view(snapshot, marks)
                self.handled[client_id] = marks
                self.snapshots[client_id, day] = seen
                return ClientDay(snapshot=seen, handled=marks)
            state = alive(self.sandboxes.get((scope.session, client_id)), now)
            held = state.handled if state else {}
            marks = changed(held, snapshot, risk_id, now, reopen=reopen)
            after = sandbox_state(snapshot, marks, state, now)
            self.sandboxes[scope.session, client_id] = after
            return sandbox_day(snapshot, after)

    async def read_day(
        self, scope: Scope, client_id: str, day: date, now: datetime
    ) -> ClientDay | None:
        checked_client_id(client_id)
        async with self._lock:
            snapshot = self.snapshots.get((client_id, day))
            if snapshot is None:
                return None
            if scope.session is None:
                return ClientDay(snapshot=snapshot, handled=self.handled.get(client_id, {}))
            state = alive(self.sandboxes.get((scope.session, client_id)), now)
            if state is None or not state.handled:
                # A visitor with no marks needs no document, and reading does not make one.
                return ClientDay(snapshot=with_view(snapshot, {}), handled={})
            if not state.current(snapshot):
                # The daily write, for a sandbox: its view of a new day or a new run.
                state = sandbox_state(snapshot, state.handled, state, now)
                self.sandboxes[scope.session, client_id] = state
            return sandbox_day(snapshot, state)

    async def save_live_check(self, check: LiveCheck) -> None:
        self.live_checks[check.domain] = check

    async def read_live_check(self, domain: str, now: datetime) -> LiveCheck | None:
        check = self.live_checks.get(domain)
        return check if check is not None and check.expires_at > now else None


__all__ = ["SHARED", "MemoryStore"]
