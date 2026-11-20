"""The bundled fallback is what `make fallback` writes today, and is the two read routes' own
answers for the twelve seeded clients on its one fixed day."""

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from domain_health.app import ClientList, ClientPage
from domain_health.seeded import load_clients
from domain_health.seeded.fallback import (
    DAY,
    FALLBACK,
    RUN_AT,
    as_text,
    build,
    check_day,
    generate,
    main,
)
from tests.paths import REPO


def test_the_committed_fallback_is_current() -> None:
    assert FALLBACK == REPO / "frontend" / "src" / "data" / "fallback.json"
    assert FALLBACK.exists(), "frontend/src/data/fallback.json is missing: run `make fallback`"
    committed = FALLBACK.read_text(encoding="utf-8")

    assert committed == generate(), (
        "frontend/src/data/fallback.json is out of date with the fixtures, the recordings or "
        "the API: run `make fallback` and commit the file"
    )


def test_two_builds_give_the_same_bytes() -> None:
    assert generate() == generate()


def test_the_fallback_holds_the_two_routes_bodies_for_every_client() -> None:
    data = asyncio.run(build())
    clients = load_clients()

    assert sorted(data) == ["clients", "generated_for_day", "snapshots"]
    assert data["generated_for_day"] == DAY.isoformat()
    listed = ClientList.model_validate(data["clients"])
    assert listed.day == DAY
    assert [client.id for client in listed.clients] == [client.id for client in clients]
    assert len(listed.clients) == 12
    assert list(data["snapshots"]) == [client.id for client in clients]
    for summary in listed.clients:
        page = ClientPage.model_validate(data["snapshots"][summary.id])
        assert page.id == summary.id
        assert page.scope == "shared"
        assert page.handled == {}
        assert page.snapshot.suppressed == []
        assert page.snapshot.day == DAY
        assert page.snapshot.domain == summary.domain
        assert page.snapshot.model_source == "recorded"
        # The clock is the fixed one: nothing in the file is the time it was made.
        assert page.snapshot.started_at == page.snapshot.finished_at == RUN_AT
        assert summary.today is not None
        assert summary.today.fixes == len(page.snapshot.fixes)
        assert summary.today.risks_visible == len(page.snapshot.visible)
        assert summary.today.risks_handled == 0


def test_the_fixed_day_is_the_first_day_of_every_cycle() -> None:
    clients = tuple(load_clients())
    assert datetime(2026, 1, 4, 6, 0, tzinfo=UTC) == RUN_AT
    check_day(clients, DAY)
    for client in clients:
        assert client.day(DAY) == client.cycle[0]

    with pytest.raises(RuntimeError, match="not the first day"):
        check_day(clients, date.fromordinal(DAY.toordinal() + 1))


def test_the_text_is_the_frontend_formatters_own_style() -> None:
    data = {"b": [1, 2], "a": {"z": None, "y": []}, "c": [{"k": "é"}], "d": ["x" * 60, "y" * 40]}

    assert as_text(data) == (
        "{\n"
        '  "a": {\n'
        '    "y": [],\n'
        '    "z": null\n'
        "  },\n"
        '  "b": [1, 2],\n'
        '  "c": [\n'
        "    {\n"
        '      "k": "é"\n'
        "    }\n"
        "  ],\n"
        '  "d": [\n'
        f'    "{"x" * 60}",\n'
        f'    "{"y" * 40}"\n'
        "  ]\n"
        "}\n"
    )


def test_the_command_writes_the_file(tmp_path: Path) -> None:
    target = tmp_path / "data" / "fallback.json"

    assert main(target) == 0
    assert target.read_text(encoding="utf-8") == generate()
