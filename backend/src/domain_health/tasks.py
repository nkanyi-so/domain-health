"""The task queue behind one interface: one task per client, each a call to the worker."""

from datetime import date, timedelta
from typing import Protocol

from domain_health.models import Frozen

# Tasks are spaced out so that twelve clients do not hit DNS and the database at one instant.
STAGGER = timedelta(seconds=2)


class QueueError(Exception):
    """The task was not enqueued."""


class TaskQueue(Protocol):
    async def enqueue(self, client_id: str, day: date, delay: timedelta) -> None:
        """Ask for the worker to run this client for this day, `delay` from now."""
        ...


class Enqueued(Frozen):
    client_id: str
    day: date
    delay: timedelta


class FakeQueue:
    """Remembers what was asked for. `failing` names clients whose enqueue raises."""

    def __init__(self, failing: frozenset[str] = frozenset()) -> None:
        self.tasks: list[Enqueued] = []
        self._failing = failing

    async def enqueue(self, client_id: str, day: date, delay: timedelta) -> None:
        if client_id in self._failing:
            raise QueueError(f"the queue refused {client_id}")
        self.tasks.append(Enqueued(client_id=client_id, day=day, delay=delay))
