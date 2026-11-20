"""The snapshot store: one document per client per day, the handled marks, and the two changes.

Everything that decides what a document holds is here, as pure functions, and both stores
(`memory.py`, `firestore.py`) call them: a store only reads, runs one of these, and writes inside
one transaction. `visible_risks` is the only place the visible list is computed.

Two scopes run the same code. The shared scope is what an admin changes: its handled marks are on
the client's document. A sandbox is one visitor's: its marks are in the visitor's own document,
which expires after a day, and nothing shared is ever written from it. In either scope a read
writes nothing and computes what is visible from the day's ranked risks and the scope's marks; the
list stored in a snapshot is what the daily write and the last click on that day left.
"""

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, field_validator

from domain_health.checks import CheckResults
from domain_health.models import Fix, Frozen, Sources
from domain_health.risks import Risk

SUPPRESS_DAYS = 30
VISIBLE_CAP = 5
SANDBOX_LIFE = timedelta(days=1)
LIVE_CHECK_LIFE = timedelta(minutes=10)

# What may be a document's name: a client's id, a visitor's session id.
_CLIENT_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{16,128}")
_HOST_NAME = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")

RisksStatus = Literal["ranked", "unavailable"]
ModelSource = Literal["recorded"]


class StoreError(Exception):
    """A change the store refuses. The message can be shown."""


class NoSnapshotError(StoreError):
    """There is no snapshot for that client and day, so there is no risk to mark."""


class UnknownRiskError(StoreError):
    """The risk named is not one of that day's ranked risks."""


class StoreBusyError(StoreError):
    """The database kept aborting the change because others were writing. Nothing was changed."""


class Scope(Frozen):
    """Whose handled marks: the shared ones (no session), or one visitor's sandbox."""

    session: str | None = None

    @field_validator("session")
    @classmethod
    def a_document_name(cls, session: str | None) -> str | None:
        if session is not None and not _SESSION_ID.fullmatch(session):
            raise ValueError("not a session id")
        return session

    @property
    def shared(self) -> bool:
        return self.session is None


SHARED = Scope()


def sandbox(session: str) -> Scope:
    try:
        return Scope(session=session)
    except ValueError as error:
        raise StoreError("not a session id") from error


def checked_domain(domain: str) -> str:
    """A domain as a document's name: a lower-case host name, nothing a path could be made of."""
    if len(domain) > 253 or not _HOST_NAME.fullmatch(domain):
        raise StoreError("not a domain name")
    return domain


def checked_client_id(client_id: str) -> str:
    if not _CLIENT_ID.fullmatch(client_id):
        raise StoreError("not a client id")
    return client_id


class HandledMark(Frozen):
    handled_at: AwareDatetime
    # The first day the risk may be shown again.
    until: date


Handled = Mapping[str, HandledMark]


class View(Frozen):
    """What a scope shows of a day's ranked risks."""

    visible: list[Risk]
    suppressed: list[Risk]


def visible_risks(ranked: list[Risk], handled: Handled, today: date) -> View:
    """The first five ranked risks that are not handled, and the handled ones.

    A mark hides its risk until `until`: handled on day 0, hidden through day 29, shown again on
    day 30. Hiding one lets the next ranked risk move up into the five.
    """
    suppressed = [risk for risk in ranked if risk.id in handled and today < handled[risk.id].until]
    hidden = {risk.id for risk in suppressed}
    shown = [risk for risk in ranked if risk.id not in hidden]
    return View(visible=shown[:VISIBLE_CAP], suppressed=suppressed)


class DayResult(Frozen):
    """What one run of the worker found for one client on one day, before any scope's view."""

    client_id: str
    domain: str
    day: date
    checks: CheckResults
    sources: Sources
    fixes: list[Fix]
    risks_status: RisksStatus
    # Why there are no risks, when the model gave nothing usable. Logged, and shown plainly.
    risks_unavailable_reason: str | None = None
    ranked: list[Risk] = Field(max_length=8)
    prompt_version: str
    model: str
    model_source: ModelSource = "recorded"
    input_hash: str
    started_at: AwareDatetime
    finished_at: AwareDatetime


class Snapshot(DayResult):
    """The stored document `clients/{client}/snapshots/{day}`: the result and the shared view."""

    visible: list[Risk]
    suppressed: list[Risk]


class SandboxState(Frozen):
    """The stored document `sandboxes/{session}/clients/{client}`: one visitor's marks. What the
    visitor sees is computed from them at each read and is not stored."""

    handled: dict[str, HandledMark] = Field(default_factory=dict)
    # Firestore's TTL policy deletes the document some time after this; a read ignores it at once.
    expires_at: AwareDatetime


class LiveCheck(Frozen):
    """The stored document `live_checks/{domain}`: a typed-domain check, kept for ten minutes."""

    domain: str
    checks: CheckResults
    fixes: list[Fix]
    checked_at: AwareDatetime

    @field_validator("domain")
    @classmethod
    def a_document_name(cls, domain: str) -> str:
        return checked_domain(domain)

    expires_at: AwareDatetime


class ClientDay(Frozen):
    """What a scope sees of one client on one day."""

    snapshot: Snapshot
    handled: dict[str, HandledMark]


def stored(result: DayResult, handled: Handled) -> Snapshot:
    """The daily write, shared scope: the day's document, with the view the marks give it."""
    view = visible_risks(result.ranked, handled, result.day)
    return Snapshot(**dict(result), visible=view.visible, suppressed=view.suppressed)


def with_view(snapshot: Snapshot, handled: Handled) -> Snapshot:
    view = visible_risks(snapshot.ranked, handled, snapshot.day)
    return snapshot.model_copy(update={"visible": view.visible, "suppressed": view.suppressed})


def sandbox_state(handled: Handled, before: SandboxState | None, now: datetime) -> SandboxState:
    """A sandbox's document after a click. It lives one day from its first click; a later click
    does not extend it. `before` is the document if it is still alive."""
    return SandboxState(
        handled=dict(handled),
        expires_at=before.expires_at if before is not None else now + SANDBOX_LIFE,
    )


def alive(state: SandboxState | None, now: datetime) -> SandboxState | None:
    """A sandbox's document, or nothing once it has expired, whether or not it is deleted yet."""
    return state if state is not None and state.expires_at > now else None


def found(snapshot: Snapshot | None) -> Snapshot:
    if snapshot is None:
        raise NoSnapshotError("there is no snapshot for that day")
    return snapshot


def changed(
    handled: Handled, snapshot: Snapshot, risk_id: str, now: datetime, *, reopen: bool
) -> dict[str, HandledMark]:
    """The marks after a handled or a reopen click on a risk of this snapshot.

    The risk has to be one the day ranked: an ID is `<type>:<domain>` built by code, and one that
    is not in the snapshot is refused, never stored. Reopening a risk that is not handled changes
    nothing.
    """
    if risk_id not in {risk.id for risk in snapshot.ranked}:
        raise UnknownRiskError("that risk is not in the snapshot")
    marks = dict(handled)
    if reopen:
        marks.pop(risk_id, None)
    else:
        today = now.astimezone(UTC).date()
        marks[risk_id] = HandledMark(handled_at=now, until=today + timedelta(days=SUPPRESS_DAYS))
    return marks


def seen(snapshot: Snapshot, handled: Handled) -> ClientDay:
    """A day as the holder of these marks sees it, computed now. A read never trusts the list
    stored in the snapshot: a mark made on another day's page changed the marks and not it."""
    return ClientDay(snapshot=with_view(snapshot, handled), handled=dict(handled))


class SnapshotStore(Protocol):
    """The database. Snapshots and handled marks change only through `write_daily` and `mark`,
    each one transaction. A read writes nothing."""

    async def write_daily(self, result: DayResult) -> Snapshot:
        """Save the day's snapshot for the shared scope. A rerun overwrites the same document."""
        ...

    async def preview_daily(self, result: DayResult) -> Snapshot:
        """What `write_daily` would save. Writes nothing."""
        ...

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
        """A handled click, or a reopen, on a risk of that day's snapshot."""
        ...

    async def read_day(
        self, scope: Scope, client_id: str, day: date, now: datetime
    ) -> ClientDay | None:
        """The day as this scope sees it, or None when there is no snapshot for it."""
        ...

    async def save_live_check(self, check: LiveCheck) -> None: ...

    async def read_live_check(self, domain: str, now: datetime) -> LiveCheck | None:
        """The cached check of a typed domain, if it is under ten minutes old."""
        ...


def live_check(domain: str, checks: CheckResults, fixes: list[Fix], now: datetime) -> LiveCheck:
    return LiveCheck(
        domain=domain,
        checks=checks,
        fixes=fixes,
        checked_at=now,
        expires_at=now + LIVE_CHECK_LIFE,
    )
