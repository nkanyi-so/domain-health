"""Prints every seeded client's every day: the input's hash and its fixes. Free, no network."""

import asyncio
from datetime import date

from domain_health.seeded import input_hash, load_clients, snapshot_input


async def lines() -> list[str]:
    out: list[str] = []
    for client in load_clients():
        for index in range(len(client.cycle)):
            # Any date that lands on this day of the cycle gives the same input.
            on = date.fromordinal(len(client.cycle) * 100_000 + index)
            snapshot = await snapshot_input(client, on)
            fixes = ", ".join(fix.type.value for fix in snapshot.fixes) or "no fix"
            out.append(f"{client.id} day {index} {input_hash(snapshot)[:16]} {fixes}")
    return out


if __name__ == "__main__":
    print("\n".join(asyncio.run(lines())))
