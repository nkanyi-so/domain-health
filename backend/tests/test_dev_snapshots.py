"""The local command that gives `make dev` today's snapshots: the worker's own run for the twelve
clients, and never anywhere but the emulator."""

import asyncio
import importlib
from datetime import UTC, datetime

import pytest

from domain_health.clock import FixedClock
from domain_health.seeded import load_clients
from domain_health.seeded.dev_snapshots import DEV_PROJECT, emulator_host, main, write_today
from domain_health.store import SHARED
from domain_health.store.memory import MemoryStore

NOW = datetime(2026, 1, 4, 6, 0, tzinfo=UTC)


def test_every_seeded_client_gets_todays_snapshot() -> None:
    async def go() -> None:
        store, clock = MemoryStore(), FixedClock(NOW)

        assert await write_today(store, clock) == 12

        for client in load_clients():
            seen = await store.read_day(SHARED, client.id, clock.today(), clock.now())
            assert seen is not None
            assert seen.snapshot.day == clock.today()
            assert seen.snapshot.model_source == "recorded"

    asyncio.run(go())


@pytest.mark.parametrize("host", ["", "firestore.googleapis.com:443", "10.0.0.5:8080"])
def test_it_refuses_anything_but_the_local_emulator(
    host: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", host)

    with pytest.raises(RuntimeError, match="emulator only"):
        emulator_host()
    with pytest.raises(RuntimeError, match="emulator only"):
        main()


def test_it_writes_to_the_project_the_local_service_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Importing the service builds one, so the environment is set first (as in test_serve.py).
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:9")
    monkeypatch.setenv("DOMAIN_HEALTH_DEV", "1")
    serve = importlib.import_module("domain_health.serve")

    assert serve.DEV_PROJECT == DEV_PROJECT
    assert emulator_host() == "127.0.0.1:9"
