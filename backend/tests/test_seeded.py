"""The twelve seeded clients: what they are, what they produce, and that it never changes."""

import json
from datetime import date, timedelta

import pytest

from domain_health.evals.cases import load_cases
from domain_health.models import SnapshotInput
from domain_health.seeded import (
    SHARED_ZONE,
    SeededClient,
    input_hash,
    load_clients,
    snapshot_input,
)
from domain_health.seeded.__main__ import lines
from domain_health.types import FixType
from tests.dns_fixtures import FIXTURES, run
from tests.paths import CASES

CLIENTS = {client.id: client for client in load_clients()}


def on_day(client: SeededClient, index: int) -> date:
    """A date that lands on this day of the client's cycle."""
    return date.fromordinal(len(client.cycle) * 100_000 + index)


def produced(client_id: str, index: int) -> SnapshotInput:
    client = CLIENTS[client_id]
    return run(snapshot_input(client, on_day(client, index)))


def fixes(client_id: str, index: int) -> list[FixType]:
    return [fix.type for fix in produced(client_id, index).fixes]


def test_there_are_twelve_invented_clients_on_reserved_domains() -> None:
    assert len(CLIENTS) == 12
    for client in CLIENTS.values():
        assert client.domain == f"{client.id}.example"
        assert client.name
        assert 2 <= len(client.cycle) <= 4
        assert all(day.note for day in client.cycle)


def test_no_seeded_client_is_an_eval_case() -> None:
    eval_domains = {case.input.domain for case in load_cases(CASES).values()}

    assert not eval_domains & {client.domain for client in CLIENTS.values()}


def test_every_zone_file_is_used_and_holds_only_reserved_names_and_documentation_addresses() -> (
    None
):
    used = {day.zone for client in CLIENTS.values() for day in client.cycle} | {SHARED_ZONE}
    on_disk = {path.stem for path in (FIXTURES / "zones").glob("*.json")}
    assert used == on_disk

    for path in (FIXTURES / "zones").glob("*.json"):
        text = path.read_text()
        assert all(name.endswith(".example") for name in json.loads(text)), path.name
        for word in text.replace('"', " ").replace(":", " ").split():
            if word.count(".") == 3 and word.replace(".", "").replace("/", "").isdecimal():
                # RFC 5737: the three address blocks set aside for documentation.
                assert word.startswith(("192.0.2.", "198.51.100.", "203.0.113.")), word


# For every fix type: a seeded client-day that produces it, and one that does not.
PRODUCED_BY: dict[FixType, tuple[tuple[str, int], tuple[str, int]]] = {
    FixType.SPF_MISSING: (("driftwood-coffee", 0), ("driftwood-coffee", 1)),
    FixType.SPF_MULTIPLE: (("inkwell-and-vine", 0), ("harbourlight-books", 0)),
    FixType.SPF_INVALID: (("tamberline-travel", 0), ("tamberline-travel", 1)),
    FixType.SPF_TOO_MANY_LOOKUPS: (("brindle-and-oak", 0), ("willowmere-pets", 0)),
    FixType.SPF_PLUS_ALL: (("copperkettle-kitchen", 0), ("oakhaven-outfitters", 0)),
    FixType.DKIM_MISSING: (("northwind-cycles", 0), ("northwind-cycles", 1)),
    FixType.DKIM_WEAK_KEY: (("copperkettle-kitchen", 0), ("oakhaven-outfitters", 0)),
    FixType.DMARC_MISSING: (("northwind-cycles", 0), ("fernhollow-garden", 0)),
    FixType.DMARC_INVALID: (("fernhollow-garden", 0), ("harbourlight-books", 0)),
    FixType.BLOCKLIST_LISTED: (("silverbrook-dental", 0), ("silverbrook-dental", 1)),
    FixType.COMPLAINT_RATE_OVER_LIMIT: (("emberglow-events", 0), ("emberglow-events", 1)),
    FixType.BOUNCE_RATE_OVER_LIMIT: (("emberglow-events", 0), ("emberglow-events", 1)),
}


def test_the_table_below_names_a_case_for_every_fix_type() -> None:
    assert list(PRODUCED_BY) == list(FixType)
    assert len(PRODUCED_BY) == 12


@pytest.mark.parametrize(
    "fix_type",
    list(FixType),
    ids=[
        f"{fix.value}: {has[0]} day {has[1]} has it, {lacks[0]} day {lacks[1]} does not"
        for fix, (has, lacks) in PRODUCED_BY.items()
    ],
)
def test_every_fix_type_has_a_fixture_case_that_produces_it_and_one_that_does_not(
    fix_type: FixType,
) -> None:
    has, lacks = PRODUCED_BY[fix_type]

    assert fix_type in fixes(*has)
    assert fix_type not in fixes(*lacks)


def test_the_near_misses_sit_right_next_to_their_fix() -> None:
    # 9 lookups is under the limit, 1,024 bits is not a weak key, 0.22% and 3.1% are under.
    assert produced("willowmere-pets", 0).checks.spf.lookup_count == 9
    assert produced("brindle-and-oak", 0).checks.spf.lookup_count == 11
    assert [k.key_bits for k in produced("oakhaven-outfitters", 0).checks.dkim.keys] == [1024]
    assert [k.key_bits for k in produced("copperkettle-kitchen", 0).checks.dkim.keys] == [512]
    assert produced("emberglow-events", 1).sources.complaint_rate_pct == 0.22


def test_one_client_is_healthy_on_every_day() -> None:
    client = CLIENTS["harbourlight-books"]

    for index in range(len(client.cycle)):
        snapshot = produced(client.id, index)
        assert snapshot.fixes == []
        assert snapshot.checks.spf.all_qualifier == "-all"
        assert snapshot.checks.dmarc.policy == "reject"
        assert [key.key_bits for key in snapshot.checks.dkim.keys] == [2048]


def test_every_fix_carries_its_source_tag_and_an_instruction() -> None:
    seen = 0
    for client in CLIENTS.values():
        for index in range(len(client.cycle)):
            for fix in produced(client.id, index).fixes:
                seen += 1
                assert fix.source in ("dns", "seeded")
                assert fix.instruction.endswith(".")
    assert seen > 12


def test_the_same_date_always_lands_on_the_same_day_and_days_follow_the_cycle() -> None:
    client = CLIENTS["silverbrook-dental"]
    start = date(2026, 11, 19)

    days = [client.day(start + timedelta(days=offset)) for offset in range(6)]

    assert days[:3] == days[3:]
    assert len({day.note for day in days[:3]}) == 3
    assert client.day(start) == client.day(start)


def test_consecutive_days_can_differ() -> None:
    assert fixes("driftwood-coffee", 0) != fixes("driftwood-coffee", 1)
    assert input_hash(produced("harbourlight-books", 0)) != input_hash(
        produced("harbourlight-books", 1)
    )


def test_all_twelve_clients_produce_the_same_output_on_two_runs() -> None:
    first, second = run(lines()), run(lines())

    assert first == second
    assert len(first) == sum(len(client.cycle) for client in CLIENTS.values())
    assert len({line.split()[0] for line in first}) == 12
    # Every client-day is a different input.
    assert len({line.split()[3] for line in first}) == len(first)


def test_the_hash_is_of_the_data_not_of_how_it_is_written() -> None:
    snapshot = produced("oakhaven-outfitters", 1)
    again = SnapshotInput.model_validate_json(snapshot.model_dump_json(indent=4))

    assert input_hash(again) == input_hash(snapshot)
    assert len(input_hash(snapshot)) == 64


def test_a_seeded_domain_must_be_reserved() -> None:
    client = CLIENTS["harbourlight-books"]

    with pytest.raises(ValueError, match=r"ends in \.example"):
        SeededClient.model_validate(
            client.model_dump() | {"domain": "harbourlight-books.example.com"}
        )


def test_the_seed_command_needs_the_project_and_a_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from domain_health.seeded.seed import main

    monkeypatch.delenv("GCP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    assert main([]) == 1
    assert "make seed" in capsys.readouterr().err
