"""DNS behind one interface: a TXT lookup that gives records, no such name, or a timeout.

Nothing outside `resolver/live.py` imports a DNS library. The checks only ever see `Resolver`.
"""

from enum import StrEnum
from typing import Protocol

from domain_health.models import Frozen

# DNS answers are untrusted text. One record is cut at this length and a name gives at most this
# many, so a hostile zone cannot make a check hold or print something huge.
MAX_RECORD_CHARS = 4096
MAX_RECORDS_PER_NAME = 20

# The most TXT lookups one live check of a domain may make, across its three checks.
MAX_QUERIES_PER_DOMAIN = 40


class TxtStatus(StrEnum):
    RECORDS = "records"
    NO_SUCH_NAME = "no_such_name"
    TIMEOUT = "timeout"


class TxtAnswer(Frozen):
    """A name that exists with no TXT record is `RECORDS` with none."""

    status: TxtStatus
    records: tuple[str, ...] = ()


class Resolver(Protocol):
    async def txt(self, name: str) -> TxtAnswer: ...


def normal_name(name: str) -> str:
    return name.strip().rstrip(".").lower()


def capped(records: list[str]) -> tuple[str, ...]:
    return tuple(record[:MAX_RECORD_CHARS] for record in records[:MAX_RECORDS_PER_NAME])


class QueryBudgetSpentError(Exception):
    """The check asked for more lookups than one domain is allowed."""


class CountingResolver:
    """Wraps a resolver and refuses the lookup after the last one allowed."""

    def __init__(self, inner: Resolver, limit: int = MAX_QUERIES_PER_DOMAIN) -> None:
        self._inner = inner
        self._limit = limit
        self.queries = 0

    async def txt(self, name: str) -> TxtAnswer:
        if self.queries >= self._limit:
            raise QueryBudgetSpentError(f"more than {self._limit} DNS lookups")
        self.queries += 1
        return await self._inner.txt(name)
