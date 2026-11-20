"""`make seed`: the twelve seeded clients' documents in the project's Firestore.

Run from the owner's machine. It is given a short-lived access token in its environment (the
`make` target takes it from the `domain-health` gcloud configuration) and uses it for this one
run. With `--count <day>` it writes nothing and prints how many snapshot documents that day has.
"""

import argparse
import asyncio
import os
import sys
from datetime import date

from domain_health.seeded import load_clients
from domain_health.store import ClientRecord
from domain_health.store.firestore import connect_with_token


async def seed(project: str, token: str) -> int:
    store = connect_with_token(project, token)
    records = [
        ClientRecord(id=client.id, name=client.name, domain=client.domain)
        for client in load_clients()
    ]
    await store.seed_clients(records)
    listed = await store.list_clients()
    print(f"seeded: {len(listed)} clients in {project}")
    return 0 if len(listed) == len(records) else 1


async def count(project: str, token: str, day: date) -> int:
    store = connect_with_token(project, token)
    found = await store.snapshot_documents(day)
    print(f"snapshot documents dated {day.isoformat()}: {len(found)}")
    for path in found:
        print(f"  {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make seed")
    parser.add_argument("--count", type=date.fromisoformat, help="count this day's snapshots")
    args = parser.parse_args(argv)
    project = os.environ.get("GCP_PROJECT_ID", "")
    token = os.environ.get("GCP_ACCESS_TOKEN", "")
    if not project or not token:
        print("run this through `make seed`: it needs the project and a token", file=sys.stderr)
        return 1
    if args.count:
        return asyncio.run(count(project, token, args.count))
    return asyncio.run(seed(project, token))


if __name__ == "__main__":
    sys.exit(main())
