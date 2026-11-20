"""`make fallback`: the snapshots the frontend bundles and serves, with a notice, when the
backend cannot be reached. Free, and it reaches nothing outside this repository.

The file holds what the frontend's two read routes would have returned for the twelve seeded
clients: the body of `GET /api/clients` and, for each client, of `GET /api/clients/{id}/snapshot`,
as the shared actor sees them with nothing handled. It is made by the code that makes the real
thing: the app is built over a store in memory, the worker runs every client's day with the kept
recordings, and the two routes are then called.

Nothing in it comes from the wall clock. The day is fixed, so the same command writes the same
bytes on any date. The deployed service never imports this module.
"""

import asyncio
import json
import sys
from collections.abc import MutableMapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from domain_health.alerts import NullAlerter
from domain_health.app import Deps, create_app
from domain_health.clock import Clock, FixedClock
from domain_health.machine_auth import StaticKeySet
from domain_health.resolver import Resolver
from domain_health.risks.model import RiskModel
from domain_health.seeded import SeededClient, load_clients
from domain_health.seeded.recordings import REPO, recorded_model
from domain_health.store import SnapshotStore
from domain_health.store.memory import MemoryStore
from domain_health.tasks import FakeQueue
from domain_health.worker import ModelFacts, run_client

FALLBACK = REPO / "frontend" / "src" / "data" / "fallback.json"

# The fallback's one day. A seeded client's state is picked by the date's ordinal, modulo the
# length of the client's cycle, and the cycles are two and three days long. On this date the
# ordinal divides by six, so every client is on the first day of its story: the day each
# problem is first there to see, before any of them clears. `check_day` refuses a day or a
# cycle that would break that.
DAY = date(2026, 1, 4)
# The time the daily schedule runs (06:00 UTC). It ends up in `started_at` and `finished_at`.
RUN_AT = datetime.combine(DAY, time(6, 0), tzinfo=UTC)

PROXY_SECRET = "fallback-build-only"  # noqa: S105
ADMIN = {"x-proxy-secret": PROXY_SECRET, "x-actor": "admin"}
# The line width the frontend's formatter keeps (`frontend/.prettierrc.json`).
WIDTH = 100


def _no_live_resolver() -> Resolver:
    raise RuntimeError("an app built offline makes no live check")


def offline_deps(
    *, store: SnapshotStore, clock: Clock, model: RiskModel, facts: ModelFacts
) -> Deps:
    """The app's parts for a command that runs on this machine alone: no queue, no alert, no
    machine caller accepted, no live DNS."""
    return Deps(
        store=store,
        clock=clock,
        clients=tuple(load_clients()),
        model=model,
        facts=facts,
        queue=FakeQueue(),
        alerter=NullAlerter(),
        keys=StaticKeySet({}),
        live_resolver=_no_live_resolver,
        proxy_secret=PROXY_SECRET,
        service_url="https://service.example",
        invoker_email="nobody@service.example",
    )


def check_day(clients: tuple[SeededClient, ...], day: date) -> None:
    """Every client is on the first day of its cycle on this date, or the build stops."""
    late = [client.id for client in clients if day.toordinal() % len(client.cycle) != 0]
    if late:
        raise RuntimeError(
            f"{day.isoformat()} is not the first day of the cycle of: {', '.join(late)}. "
            "Pick a date whose ordinal divides by every cycle's length."
        )


async def get(app: FastAPI, path: str, headers: dict[str, str]) -> Any:
    """The JSON body of one GET, asked of the app itself: no server, no socket, no HTTP client."""
    sent: list[MutableMapping[str, Any]] = []

    async def receive() -> MutableMapping[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (name.encode("ascii"), value.encode("ascii")) for name, value in headers.items()
        ],
        "client": ("127.0.0.1", 0),
        "server": ("service.example", 443),
    }
    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    if status != 200:
        raise RuntimeError(f"GET {path} gave {status}: {body.decode('utf-8', 'replace')}")
    return json.loads(body)


async def build() -> dict[str, Any]:
    """The fallback as data: the day, the client list and every client's page."""
    model, prompt, model_name = recorded_model()
    facts = ModelFacts(prompt_version=prompt.version, model=model_name)
    deps = offline_deps(store=MemoryStore(), clock=FixedClock(RUN_AT), model=model, facts=facts)
    check_day(deps.clients, DAY)
    for client in deps.clients:
        await run_client(
            client, DAY, model=deps.model, facts=deps.facts, store=deps.store, clock=deps.clock
        )
    app = create_app(deps)
    return {
        "generated_for_day": DAY.isoformat(),
        "clients": await get(app, "/api/clients", ADMIN),
        "snapshots": {
            client.id: await get(app, f"/api/clients/{client.id}/snapshot", ADMIN)
            for client in deps.clients
        },
    }


def _scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _lines(value: object, indent: int, before: str, after: str) -> list[str]:
    """`value` as lines of JSON, the way the frontend's formatter writes it: keys sorted, two
    spaces, an object always one key to a line, a list of plain values on one line when it fits.
    `before` is the key in front of the first line and `after` the comma behind the last."""
    pad = "  " * indent
    if isinstance(value, dict) and value:
        lines = [f"{pad}{before}{{"]
        keys = sorted(value)
        for key in keys:
            comma = "" if key == keys[-1] else ","
            lines += _lines(value[key], indent + 1, f"{_scalar(key)}: ", comma)
        return [*lines, f"{pad}}}{after}"]
    if isinstance(value, list) and value:
        if not any(isinstance(item, (dict, list)) and item for item in value):
            flat = f"{pad}{before}[{', '.join(_scalar(item) for item in value)}]{after}"
            if len(flat) <= WIDTH:
                return [flat]
        lines = [f"{pad}{before}["]
        for index, item in enumerate(value):
            lines += _lines(item, indent + 1, "", "" if index == len(value) - 1 else ",")
        return [*lines, f"{pad}]{after}"]
    return [f"{pad}{before}{_scalar(value)}{after}"]


def as_text(data: object) -> str:
    """The file's exact text, ending in one newline."""
    return "\n".join(_lines(data, 0, "", "")) + "\n"


def generate() -> str:
    return as_text(asyncio.run(build()))


def main(path: Path = FALLBACK) -> int:
    text = generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.name} for {DAY.isoformat()}: {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
