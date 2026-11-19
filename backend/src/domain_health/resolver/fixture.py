"""Zone data from the repository: what the seeded clients and the tests resolve through."""

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import TypeAdapter

from domain_health.resolver import TxtAnswer, TxtStatus, answer_with, normal_name

Zone = dict[str, list[str]]
_ZONE = TypeAdapter(Zone)


def load_zone(paths: Iterable[Path]) -> Zone:
    """The zone files merged; a name in a later file replaces the same name in an earlier one."""
    zone: Zone = {}
    for path in paths:
        zone.update(_ZONE.validate_python(json.loads(path.read_text(encoding="utf-8"))))
    return zone


class FixtureResolver:
    """A name in the zone answers with its records; any other name does not exist.

    `timeouts` names lookups that never answer, for tests of what a check does then.
    """

    def __init__(self, zone: Mapping[str, Sequence[str]], timeouts: Iterable[str] = ()) -> None:
        self._zone = {normal_name(name): list(records) for name, records in zone.items()}
        self._timeouts = {normal_name(name) for name in timeouts}
        self.asked: list[str] = []

    async def txt(self, name: str) -> TxtAnswer:
        name = normal_name(name)
        self.asked.append(name)
        if name in self._timeouts:
            return TxtAnswer(status=TxtStatus.TIMEOUT)
        if name not in self._zone:
            return TxtAnswer(status=TxtStatus.NO_SUCH_NAME)
        return answer_with(self._zone[name])
