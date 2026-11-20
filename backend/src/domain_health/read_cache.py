"""A short cache for the answers of the public read routes, kept in the service's own memory.

Every public page load used to read Firestore; a repeated load now costs no read for
`TIME_TO_LIVE`. The cache holds at most `MAX_ENTRIES` answers and drops the oldest first, so a
caller who asks for many different pages cannot grow it.

It is coherent because the service runs as at most one instance: the instance that takes a
handled or reopen click, or a worker run, is the one that holds the cache, and it drops what the
write made stale before it answers. If the service ever ran as more than one instance, a click or
a worker run taken by another instance would show here up to `TIME_TO_LIVE` late.

Pure and synchronous. The caller says what time it is, so a test can.
"""

from collections.abc import Callable, Hashable
from datetime import datetime, timedelta

TIME_TO_LIVE = timedelta(seconds=30)
MAX_ENTRIES = 256

type Key = tuple[Hashable, ...]


class ReadCache[Value]:
    def __init__(self, time_to_live: timedelta = TIME_TO_LIVE, max_entries: int = MAX_ENTRIES):
        if max_entries < 1:
            raise ValueError("a cache holds at least one entry")
        self.time_to_live = time_to_live
        self.max_entries = max_entries
        # In the order they were put: a dict keeps it, so the first key is the oldest.
        self._entries: dict[Key, tuple[datetime, Value]] = {}
        self._drops = 0

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def drops(self) -> int:
        """How many times `drop` or `clear` has been called.

        A caller that reads the store across an `await` notes this before the read and does not
        `put` if it has moved: the answer it holds may be older than the write that dropped.
        """
        return self._drops

    def get(self, key: Key, now: datetime) -> Value | None:
        """The answer kept for `key`, or None when there is none or it is too old."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        put_at, value = entry
        # A clock that went backwards is not trusted either.
        if not timedelta(0) <= now - put_at < self.time_to_live:
            del self._entries[key]
            return None
        return value

    def put(self, key: Key, value: Value, now: datetime) -> None:
        self._entries.pop(key, None)
        self._entries[key] = (now, value)
        while len(self._entries) > self.max_entries:
            del self._entries[next(iter(self._entries))]

    def drop(self, matches: Callable[[Key], bool]) -> None:
        """Forget every entry whose key `matches`."""
        self._drops += 1
        for key in [key for key in self._entries if matches(key)]:
            del self._entries[key]

    def clear(self) -> None:
        self._drops += 1
        self._entries.clear()
