"""The clock behind one interface, so a test can say what day it is. Days are UTC days."""

from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


class FixedClock:
    """A clock a test sets. `at` must carry a time zone."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("a clock's time carries a time zone")
        self.at = at

    def now(self) -> datetime:
        return self.at

    def today(self) -> date:
        return self.at.astimezone(UTC).date()
