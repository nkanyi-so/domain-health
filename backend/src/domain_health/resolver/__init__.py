"""DNS behind one interface: a TXT lookup that gives records, no such name, or a timeout.

Nothing outside `resolver/live.py` imports a DNS library. The checks only ever see `Resolver`.
"""

from enum import StrEnum
from typing import Protocol

from domain_health.models import Frozen

# DNS answers are untrusted text, so there is a limit to how much of it a check will read: this
# many records at one name, each this long. Real zones sit far below both (a busy domain's top
# name holds a few dozen records). An answer over either limit is not cut and read in part, which
# could hide the one record that matters: it is `TOO_LARGE`, and the check is not made.
MAX_RECORD_CHARS = 4096
MAX_RECORDS_PER_NAME = 100

# The most TXT lookups one live check of a domain may make, across its three checks.
MAX_QUERIES_PER_DOMAIN = 40


class TxtStatus(StrEnum):
    RECORDS = "records"
    NO_SUCH_NAME = "no_such_name"
    TIMEOUT = "timeout"
    TOO_LARGE = "too_large"


class TxtAnswer(Frozen):
    """A name that exists with no TXT record is `RECORDS` with none."""

    status: TxtStatus
    records: tuple[str, ...] = ()


class Resolver(Protocol):
    async def txt(self, name: str) -> TxtAnswer: ...


def normal_name(name: str) -> str:
    return name.strip().rstrip(".").lower()


def answer_with(records: list[str]) -> TxtAnswer:
    """The records a name answered with, whole, or `TOO_LARGE`. Never a part of them."""
    if len(records) > MAX_RECORDS_PER_NAME or any(len(r) > MAX_RECORD_CHARS for r in records):
        return TxtAnswer(status=TxtStatus.TOO_LARGE)
    return TxtAnswer(status=TxtStatus.RECORDS, records=tuple(records))


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
