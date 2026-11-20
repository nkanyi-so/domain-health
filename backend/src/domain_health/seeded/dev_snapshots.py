"""Today's snapshots for the twelve seeded clients, written to the local Firestore emulator.

`make dev` runs this once before it starts the two servers: the emulator starts empty and no
schedule runs locally, so without it every client would read "No snapshot today". It is the
worker's own `run_client` with the kept recordings, exactly what the daily job does.

It refuses to run unless the emulator's address is set and local, so it can never write to a
real project. The deployed service never imports this module.
"""

import asyncio
import os
import sys

from domain_health.clock import Clock, SystemClock
from domain_health.seeded import load_clients
from domain_health.seeded.recordings import recorded_model
from domain_health.store import SnapshotStore
from domain_health.worker import ModelFacts, run_client

# The emulator's project, the one `make dev` serves (`serve.DEV_PROJECT`; a test keeps them equal).
DEV_PROJECT = "demo-domain-health"


def emulator_host() -> str:
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    if not host.startswith(("127.0.0.1:", "localhost:")):
        raise RuntimeError("this writes to the Firestore emulator only: run it through `make dev`")
    return host


async def write_today(store: SnapshotStore, clock: Clock) -> int:
    """Runs every seeded client's day, today, into the store. Returns how many were written."""
    model, prompt, model_name = recorded_model()
    facts = ModelFacts(prompt_version=prompt.version, model=model_name)
    clients = load_clients()
    for client in clients:
        await run_client(client, clock.today(), model=model, facts=facts, store=store, clock=clock)
    return len(clients)


def main() -> int:
    emulator_host()
    # Imported here, after the check, so nothing is connected before the address is known local.
    from domain_health.store.firestore import connect

    clock = SystemClock()
    written = asyncio.run(write_today(connect(DEV_PROJECT), clock))
    print(f"local emulator: {written} snapshots written for {clock.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
