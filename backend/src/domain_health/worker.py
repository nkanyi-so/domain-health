"""The worker's core: one seeded client, one day. Checks, rules, model, snapshot.

A function, so the scheduled endpoint (Phase 4) and a test run the same thing. Run twice for one
day it writes the same document twice. With `dry_run` it does everything and writes nothing.

`python -m domain_health.worker <client-id>` is a dry run from the command line: it prints the
document a run would write and touches no database.
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

from domain_health.clock import Clock, SystemClock
from domain_health.models import Frozen
from domain_health.risks import Risk
from domain_health.risks.model import (
    RecordedRiskModel,
    RiskModel,
    RisksUnavailableError,
    input_hash,
    load_calls,
)
from domain_health.risks.prompt import load_prompt
from domain_health.seeded import SeededClient, checked, load_clients
from domain_health.store import DayResult, Snapshot, SnapshotStore
from domain_health.store.memory import MemoryStore

log = logging.getLogger(__name__)


class ModelFacts(Frozen):
    """Which prompt version and model the risks came from. Stored with every snapshot."""

    prompt_version: str
    model: str


async def run_client(
    client: SeededClient,
    on: date,
    *,
    model: RiskModel,
    facts: ModelFacts,
    store: SnapshotStore,
    clock: Clock,
    dry_run: bool = False,
) -> Snapshot:
    """Run one client's day and save it. Returns the document written, or, on a dry run, the
    document that would have been.

    A model that gives nothing usable does not fail the run: the snapshot is saved with its
    fixes and no risks, says so, and the reason is logged.
    """
    started_at = clock.now()
    results, snapshot_input = await checked(client, on)
    ranked: list[Risk] = []
    reason: str | None = None
    try:
        ranked = await model.rank(snapshot_input)
    except RisksUnavailableError as error:
        reason = str(error)
        log.warning("risks unavailable for %s on %s: %s", client.id, on.isoformat(), reason)
    result = DayResult(
        client_id=client.id,
        domain=client.domain,
        day=on,
        checks=results,
        sources=snapshot_input.sources,
        fixes=snapshot_input.fixes,
        risks_status="ranked" if reason is None else "unavailable",
        risks_unavailable_reason=reason,
        ranked=ranked,
        prompt_version=facts.prompt_version,
        model=facts.model,
        input_hash=input_hash(snapshot_input),
        started_at=started_at,
        finished_at=clock.now(),
    )
    if dry_run:
        return await store.preview_daily(result)
    return await store.write_daily(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m domain_health.worker", description="A dry run: prints, writes nothing."
    )
    parser.add_argument("client", help="a seeded client's id")
    parser.add_argument("--date", type=date.fromisoformat, help="the day to run (default: today)")
    parser.add_argument("--prompt", type=Path, required=True, help="the prompt version file")
    parser.add_argument("--model", required=True, help="the model the recordings were made on")
    parser.add_argument("--recordings", type=Path, help="a folder of recorded calls to replay")
    args = parser.parse_args(argv)

    clients = {client.id: client for client in load_clients()}
    if args.client not in clients:
        print(f"no seeded client {args.client!r}. One of: {', '.join(clients)}", file=sys.stderr)
        return 2
    prompt = load_prompt(args.prompt)
    calls = load_calls(args.recordings) if args.recordings else []
    clock = SystemClock()
    snapshot = asyncio.run(
        run_client(
            clients[args.client],
            args.date or clock.today(),
            model=RecordedRiskModel(prompt, args.model, calls),
            facts=ModelFacts(prompt_version=prompt.version, model=args.model),
            store=MemoryStore(),
            clock=clock,
            dry_run=True,
        )
    )
    print("dry run: nothing was written. The document a run would write:")
    print(snapshot.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
