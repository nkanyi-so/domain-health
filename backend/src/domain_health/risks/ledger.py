"""The spend ledger: every paid call is checked before it is made and written down after.

The check is at the most the call could cost, against the cap in `docs/STANDING.md`. A call that
could take the total past the cap is not made. The ledger is a committed file, so spend carries
from one session to the next.
"""

import json
import re
from pathlib import Path

from domain_health.models import Frozen

# US dollars per million tokens, in and out (decision 0002).
PRICES: dict[str, tuple[float, float]] = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
}
_CAP_LINE = re.compile(r"^spend-cap-usd:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)


class SpendCapError(Exception):
    """The next call could take the total past the cap. It was not made."""


class LedgerEntry(Frozen):
    at: str
    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """What a call costs. A model with no known price cannot be paid for."""
    if model not in PRICES:
        raise SpendCapError(f"no price is known for {model}, so no call to it is made")
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def most_tokens(text: str) -> int:
    """An upper bound on the tokens in a text: no token is shorter than one byte."""
    return len(text.encode("utf-8"))


def standing_cap(standing: Path) -> float:
    """The owner's cap, from the `spend-cap-usd:` line. No line, no spend."""
    found = _CAP_LINE.search(standing.read_text(encoding="utf-8"))
    if not found:
        raise SpendCapError(f"no spend-cap-usd line in {standing.name}, so nothing may be spent")
    return float(found.group(1))


class Ledger:
    def __init__(self, path: Path, cap_usd: float) -> None:
        self._path = path
        self._cap = cap_usd
        self._reserved = 0.0

    def entries(self) -> list[LedgerEntry]:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [LedgerEntry.model_validate(json.loads(line)) for line in lines if line.strip()]

    def spent(self) -> float:
        return sum(entry.cost_usd for entry in self.entries())

    def reserve(self, model: str, most_input_tokens: int, most_output_tokens: int) -> float:
        """Set aside the most this call could cost, or refuse it. Call before the request."""
        worst = cost_usd(model, most_input_tokens, most_output_tokens)
        total = self.spent() + self._reserved + worst
        if total > self._cap:
            raise SpendCapError(
                f"this call could bring spend to ${total:.4f}, past the cap of ${self._cap:.2f}"
            )
        self._reserved += worst
        return worst

    def settle(self, reserved: float, entry: LedgerEntry | None) -> None:
        """Release what was set aside and write down what the call cost. A call that never
        reached the model is settled with no entry."""
        self._reserved = max(0.0, self._reserved - reserved)
        if entry is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as file:
            file.write(entry.model_dump_json() + "\n")
