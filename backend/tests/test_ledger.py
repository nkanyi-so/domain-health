from pathlib import Path

import pytest

from domain_health.risks.ledger import (
    PRICES,
    Ledger,
    LedgerEntry,
    SpendCapError,
    cost_usd,
    most_tokens,
    spend_cap,
)
from tests.paths import REPO


def entry(cost: float) -> LedgerEntry:
    return LedgerEntry(
        at="2026-11-19T12:00:00+00:00",
        purpose="test",
        model="gpt-6-luna",
        input_tokens=1,
        output_tokens=1,
        cost_usd=cost,
    )


def test_cost_is_tokens_times_the_price_per_million() -> None:
    assert PRICES["gpt-6-luna"] == (0.10, 0.50)
    assert PRICES["gpt-6.1-terra"] == (1.00, 5.00)
    assert cost_usd("gpt-6-luna", 2_000_000, 1_000_000) == pytest.approx(0.70)
    assert cost_usd("gpt-6.1-terra", 2000, 600) == pytest.approx(0.005)


def test_a_model_with_no_known_price_is_never_called() -> None:
    with pytest.raises(SpendCapError, match="no price"):
        cost_usd("some-other-model", 1, 1)


def test_the_token_bound_is_never_under_the_real_count() -> None:
    # No token is shorter than a byte, so bytes bound tokens from above.
    assert most_tokens("abc") == 3
    assert most_tokens("é") == 2


def test_the_cap_is_the_line_in_the_spend_cap_file(tmp_path: Path) -> None:
    assert spend_cap(REPO / "evals" / "spend-cap.txt") == 10.0

    other = tmp_path / "spend-cap.txt"
    other.write_text("mode: gated\n", encoding="utf-8")
    with pytest.raises(SpendCapError, match="nothing may be spent"):
        spend_cap(other)


def test_a_call_under_the_cap_is_reserved_and_then_written_down(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl", cap_usd=1.0)

    reserved = ledger.reserve("gpt-6-luna", 10_000, 2_000)
    ledger.settle(reserved, entry(0.0005))

    assert reserved == pytest.approx(0.002)
    assert ledger.spent() == pytest.approx(0.0005)
    assert [e.purpose for e in ledger.entries()] == ["test"]


def test_the_call_that_could_pass_the_cap_is_refused_before_it_is_made(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl", cap_usd=0.01)
    ledger.settle(0.0, entry(0.009))

    # The worst case of the next call is $0.002: 0.009 + 0.002 is past the cap.
    with pytest.raises(SpendCapError, match="past the cap"):
        ledger.reserve("gpt-6-luna", 10_000, 2_000)

    assert ledger.spent() == pytest.approx(0.009)


def test_calls_in_flight_count_against_the_cap_at_their_worst(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl", cap_usd=0.005)

    first = ledger.reserve("gpt-6-luna", 10_000, 2_000)
    second = ledger.reserve("gpt-6-luna", 10_000, 2_000)
    with pytest.raises(SpendCapError):
        ledger.reserve("gpt-6-luna", 10_000, 2_000)

    # Once one comes back cheaper than its worst case, there is room again.
    ledger.settle(first, entry(0.0001))
    ledger.settle(second, entry(0.0001))
    ledger.reserve("gpt-6-luna", 10_000, 2_000)


def test_spend_carries_over_in_the_file_between_sessions(tmp_path: Path) -> None:
    path = tmp_path / "evals" / "ledger.jsonl"
    Ledger(path, cap_usd=1.0).settle(0.0, entry(0.25))
    Ledger(path, cap_usd=1.0).settle(0.0, entry(0.5))

    later = Ledger(path, cap_usd=1.0)

    assert later.spent() == pytest.approx(0.75)
    with pytest.raises(SpendCapError):
        later.reserve("gpt-6.1-terra", 100_000, 40_000)


def test_a_call_that_never_reached_the_model_leaves_no_entry(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl", cap_usd=0.003)

    ledger.settle(ledger.reserve("gpt-6-luna", 10_000, 2_000), None)

    assert ledger.entries() == []
    ledger.reserve("gpt-6-luna", 10_000, 2_000)
