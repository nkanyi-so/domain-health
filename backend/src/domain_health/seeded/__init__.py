"""The twelve seeded clients: invented companies on reserved `.example` domains.

Each client has a small fixed cycle of days. A day names the zone the client's DNS answers come
from that day and holds that day's seeded sources (reputation, rates, volume, blocklist, age),
which on the real system come from accounts the demo does not have. The same date always gives the
same day, so a run can be repeated and consecutive days can differ.

Seeded clients resolve through `FixtureResolver` only. Nothing here reaches real DNS.
"""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from domain_health.checks.run import run_checks
from domain_health.models import Frozen, SnapshotInput, Sources
from domain_health.resolver.fixture import FixtureResolver, load_zone
from domain_health.rules import fix_list

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
SEEDED_SUFFIX = ".example"
# Records of the invented mail services the clients' SPF records include. In every zone.
SHARED_ZONE = "_services"


class SeededDay(Frozen):
    zone: str
    sources: Sources
    note: str


class SeededClient(Frozen):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str
    domain: str
    cycle: list[SeededDay] = Field(min_length=1)

    @model_validator(mode="after")
    def domain_is_reserved(self) -> Self:
        if not self.domain.endswith(SEEDED_SUFFIX):
            raise ValueError(f"a seeded domain ends in {SEEDED_SUFFIX}")
        return self

    def day(self, on: date) -> SeededDay:
        return self.cycle[on.toordinal() % len(self.cycle)]


def load_clients(fixtures: Path = FIXTURES) -> list[SeededClient]:
    """Every seeded client, in the order of its id."""
    clients = [
        SeededClient.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((fixtures / "clients").glob("*.json"))
    ]
    for wanted in ("id", "domain"):
        values = [getattr(client, wanted) for client in clients]
        if len(set(values)) != len(values):
            raise ValueError(f"two seeded clients share one {wanted}")
    return clients


def resolver_for(day: SeededDay, fixtures: Path = FIXTURES) -> FixtureResolver:
    zones = fixtures / "zones"
    return FixtureResolver(load_zone([zones / f"{SHARED_ZONE}.json", zones / f"{day.zone}.json"]))


async def snapshot_input(
    client: SeededClient, on: date, fixtures: Path = FIXTURES
) -> SnapshotInput:
    """What the risk model receives for this client on this date: checks, sources, fixes."""
    day = client.day(on)
    results = await run_checks(resolver_for(day, fixtures), client.domain)
    checks = results.model_input()
    fixes = fix_list(checks.spf, checks.dkim, checks.dmarc, day.sources)
    return SnapshotInput(domain=client.domain, checks=checks, sources=day.sources, fixes=fixes)


def input_hash(snapshot: SnapshotInput) -> str:
    """One input, one hash: the same data gives the same hash on any machine."""
    canonical = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
