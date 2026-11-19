"""The comparison with the rules-only baseline, and the proof that a looser table cannot pass it.

Part of the measure: the owner changes this file.
"""

from itertools import combinations

from domain_health.evals.cases import load_cases
from domain_health.evals.comparison import (
    baseline_run,
    better_than_baseline,
    score_open_run,
)
from domain_health.evals.table import table_label
from domain_health.types import RiskType
from tests.paths import CASES

OPEN = {name: case for name, case in load_cases(CASES).items() if case.set == "open"}
BASELINE = baseline_run(OPEN)
BANDS = {name: table_label(case.input) for name, case in OPEN.items()}
TYPES = list(RiskType)


def loosened(extra: frozenset[RiskType]) -> dict[str, list[RiskType]]:
    """The baseline, also returning what the bands call acceptable for the types in `extra`."""
    run: dict[str, list[RiskType]] = {}
    for name, bands in BANDS.items():
        also = [risk for risk in TYPES if risk in extra and risk in bands.acceptable]
        run[name] = [*BASELINE[name], *also][:8]
    return run


def perfect() -> dict[str, list[RiskType]]:
    return {name: list(case.label.expected) for name, case in OPEN.items()}


def test_the_baseline_does_not_beat_itself() -> None:
    assert not better_than_baseline(OPEN, [BASELINE] * 3)


def test_the_written_calls_beat_the_baseline() -> None:
    assert better_than_baseline(OPEN, [perfect()] * 3)


def test_no_loosened_table_beats_the_baseline() -> None:
    """Every table made by also returning any set of "acceptable" bands must fail.

    If one passed, beating the baseline would show a moved threshold, not judgment.
    """
    passing = [
        sorted(risk.value for risk in subset)
        for size in range(len(TYPES) + 1)
        for subset in combinations(TYPES, size)
        if better_than_baseline(OPEN, [loosened(frozenset(subset))] * 3)
    ]

    assert passing == []


def test_one_good_run_out_of_three_is_not_enough() -> None:
    assert not better_than_baseline(OPEN, [perfect(), BASELINE, BASELINE])


def test_a_gain_from_one_case_is_not_enough() -> None:
    gaining = [
        name for name, case in OPEN.items() if set(case.label.expected) - set(BASELINE[name])
    ]
    run = dict(BASELINE)
    run[gaining[0]] = list(OPEN[gaining[0]].label.expected)

    assert score_open_run(OPEN, run, BASELINE).cases_gained == 1
    assert not better_than_baseline(OPEN, [run] * 3)


def test_one_harmful_answer_fails_the_comparison() -> None:
    trap = next(name for name, case in OPEN.items() if case.label.wrong)
    run = perfect()
    run[trap] = [*run[trap], OPEN[trap].label.wrong[0]]

    assert not better_than_baseline(OPEN, [run, perfect(), perfect()])


def test_harmful_is_counted_past_the_first_five() -> None:
    trap = next(name for name, case in OPEN.items() if case.label.wrong)
    padding = [risk for risk in TYPES if risk not in OPEN[trap].label.wrong][:5]
    run = dict(BASELINE)
    run[trap] = [*padding, OPEN[trap].label.wrong[0]]

    assert score_open_run(OPEN, run, BASELINE).harmful == 1


def test_the_gain_can_come_from_several_open_cases() -> None:
    gaining = [
        name for name, case in OPEN.items() if set(case.label.expected) - set(BASELINE[name])
    ]

    assert len(gaining) >= 6


def test_every_note_names_the_types_its_call_moves() -> None:
    for name, case in OPEN.items():
        bands = BANDS[name]
        for risk in TYPES:
            placed = [
                risk in lst
                for lst in (case.label.expected, case.label.acceptable, case.label.wrong)
            ]
            by_bands = [risk in lst for lst in (bands.expected, bands.acceptable, bands.wrong)]
            if placed != by_bands:
                assert f"`{risk.value}`" in case.note, (
                    f"{name}: the note does not name {risk.value}"
                )
