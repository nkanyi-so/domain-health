"""The service's start-up wiring, as far as it can be built without Google Cloud."""

import asyncio
import importlib
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain_health.seeded.recordings import recorded_model


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The module, imported as `make dev` imports it. Importing it builds a service, so the
    environment is set first. No emulator is listening there: building must not need one."""
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:9")
    monkeypatch.setenv("DOMAIN_HEALTH_DEV", "1")
    return importlib.import_module("domain_health.serve")


def test_the_recorded_model_can_be_built_inside_a_running_event_loop() -> None:
    # `make dev` runs the server with --reload, which imports the service inside its loop.
    async def go() -> str:
        _, prompt, _ = recorded_model()
        return prompt.version

    assert asyncio.run(go()) == recorded_model()[1].version


def test_the_development_service_is_built_inside_a_running_loop_and_answers(
    serve: ModuleType,
) -> None:
    async def go() -> FastAPI:
        app: FastAPI = serve.build()
        return app

    client = TestClient(asyncio.run(go()))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/clients").status_code == 401
    # No machine caller is accepted locally at all.
    assert client.post("/internal/dispatch").status_code == 401


def test_the_development_service_runs_against_the_emulator_only(
    serve: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)

    with pytest.raises(RuntimeError, match="emulator only"):
        serve.development()
