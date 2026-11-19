"""The comparison with the rules-only baseline, and what is and is not proved about it.

Part of the measure: the owner changes this file.
"""

import tomllib
from collections.abc import Callable
from itertools import combinations

import pytest

from domain_health.evals import comparison
from domain_health.evals.cases import EvalCase, load_cases
from domain_health.evals.comparison import (
    OpenScore,
    baseline_run,
    better_than_baseline,
    mean_precision,
    score_open_run,
)
from domain_health.evals.table import baseline_risks, table_label
from domain_health.types import RiskType
from tests.paths import BARS, CASES

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


def test_no_table_that_also_returns_acceptable_bands_beats_the_baseline() -> None:
    """Every table made by also returning any set of "acceptable" bands must fail.

    This is one family of looser tables, not all of them: see the test after this one.
    """
    passing = [
        sorted(risk.value for risk in subset)
        for size in range(len(TYPES) + 1)
        for subset in combinations(TYPES, size)
        if better_than_baseline(OPEN, [loosened(frozenset(subset))] * 3)
    ]

    assert passing == []


def test_a_table_with_one_number_moved_does_beat_the_baseline() -> None:
    """The known limit (decision 0012), kept as a test so no document can claim otherwise.

    The baseline, raising `volume_spike` from a ratio of 1.3 at 1,000 messages a week or more,
    passes the comparison with no model. If this ever fails, the cases changed and the
    sentences in docs/SPEC.md and decision 0012 that quote it need the owner.
    """
    run: dict[str, list[RiskType]] = {}
    for name, case in OPEN.items():
        sources = case.input.sources
        ratio = sources.volume_7d / sources.volume_prev_7d if sources.volume_prev_7d else 2.0
        risks = list(BASELINE[name])
        if ratio >= 1.3 and sources.volume_7d >= 1000 and RiskType.VOLUME_SPIKE not in risks:
            risks.append(RiskType.VOLUME_SPIKE)
        run[name] = risks
    score = score_open_run(OPEN, run, BASELINE)

    assert (score.found, score.expected, score.harmful) == (21, 25, 0)
    assert better_than_baseline(OPEN, [run] * 3)


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
    trap, padding = next(
        (name, not_wrong[:5])
        for name, case in OPEN.items()
        if case.label.wrong
        and len(not_wrong := [risk for risk in TYPES if risk not in case.label.wrong]) >= 5
    )
    run = dict(BASELINE)
    run[trap] = [*padding, OPEN[trap].label.wrong[0]]

    assert len(padding) == 5
    assert run[trap][5] in OPEN[trap].label.wrong
    assert score_open_run(OPEN, run, BASELINE).harmful == 1


def test_precision_is_the_mean_of_the_runs_not_pooled() -> None:
    full = OpenScore(found=10, expected=10, returned=10, precise=10, harmful=0, cases_gained=2)
    one_noise = OpenScore(found=0, expected=10, returned=1, precise=0, harmful=0, cases_gained=0)

    # Pooled this would be 20 of 21; as the mean of the runs it is two thirds, under the bar.
    assert mean_precision([full, full, one_noise]) == pytest.approx(2 / 3)
    assert mean_precision([full, full, full]) == 1.0


def test_the_comparison_itself_uses_the_mean_of_the_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two full runs and one noisy one: pooled precision passes the bar, the mean does not."""
    base = OpenScore(found=10, expected=20, returned=10, precise=10, harmful=0, cases_gained=0)
    full = OpenScore(found=14, expected=20, returned=50, precise=50, harmful=0, cases_gained=3)
    noisy = OpenScore(found=14, expected=20, returned=10, precise=3, harmful=0, cases_gained=3)
    # The comparison scores the baseline first, then the runs in the order given.
    scores = iter([base, full, full, noisy])
    monkeypatch.setattr(comparison, "score_open_run", lambda *_: next(scores))

    assert comparison.PRECISION_BAR <= (50 + 50 + 3) / (50 + 50 + 10)  # pooled would pass
    assert not better_than_baseline(OPEN, [BASELINE] * 3)


def test_with_precise_runs_the_same_gains_do_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    base = OpenScore(found=10, expected=20, returned=10, precise=10, harmful=0, cases_gained=0)
    full = OpenScore(found=14, expected=20, returned=50, precise=50, harmful=0, cases_gained=3)
    scores = iter([base, full, full, full])
    monkeypatch.setattr(comparison, "score_open_run", lambda *_: next(scores))

    assert better_than_baseline(OPEN, [BASELINE] * 3)


def test_a_run_that_returns_nothing_has_no_precision() -> None:
    empty = OpenScore(found=0, expected=10, returned=0, precise=0, harmful=0, cases_gained=0)

    assert mean_precision([empty, empty, empty]) is None


def test_the_comparison_is_defined_over_three_runs() -> None:
    with pytest.raises(ValueError, match="3 runs"):
        better_than_baseline(OPEN, [perfect()] * 2)


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


# --- what the four bars do and do not show (docs/SPEC.md, "What the comparison does not show") ---

ALL = load_cases(CASES)
BARS_FILE = tomllib.loads(BARS.read_text(encoding="utf-8"))


def scored(pick: Callable[[EvalCase], list[RiskType]]) -> tuple[float, float, int]:
    """Coverage, precision and harmful for one deterministic run over all the cases."""
    found = expected = returned = precise = harmful = 0
    for case in ALL.values():
        everything = pick(case)
        first_five = set(everything[:5])
        wanted = set(case.label.expected)
        expected += len(wanted)
        found += len(first_five & wanted)
        returned += len(first_five)
        precise += len(first_five & (wanted | set(case.label.acceptable)))
        harmful += len(set(everything) & set(case.label.wrong))
    return found / expected, precise / returned, harmful


def plain_baseline(case: EvalCase) -> list[RiskType]:
    return baseline_risks(case.input)


def one_number_moved(case: EvalCase) -> list[RiskType]:
    sources = case.input.sources
    ratio = sources.volume_7d / sources.volume_prev_7d if sources.volume_prev_7d else 2.0
    risks = baseline_risks(case.input)
    if ratio >= 1.3 and sources.volume_7d >= 1000 and RiskType.VOLUME_SPIKE not in risks:
        risks.append(RiskType.VOLUME_SPIKE)
    return risks


def everything_the_bands_allow(case: EvalCase) -> list[RiskType]:
    bands = table_label(case.input)
    return [*bands.expected, *bands.acceptable][:8]


@pytest.mark.parametrize("pick", [plain_baseline, one_number_moved])
def test_a_table_with_no_model_meets_the_bars(pick: Callable[[EvalCase], list[RiskType]]) -> None:
    """Pins the spec's sentence: the bars alone do not tell a model from a table.

    A table is deterministic, so its stability is 1.00 and only three bars need computing.
    """
    coverage, precision, harmful = scored(pick)

    assert coverage >= BARS_FILE["coverage"]["value"]
    assert precision >= BARS_FILE["precision"]["value"]
    assert harmful == BARS_FILE["harmful"]["value"]


def test_the_two_tables_score_what_the_spec_says() -> None:
    plain = scored(plain_baseline)
    moved = scored(one_number_moved)

    assert (round(plain[0], 2), plain[1], plain[2]) == (0.88, 1.0, 0)
    assert (round(moved[0], 2), round(moved[1], 2), moved[2]) == (0.94, 0.97, 0)


def test_naming_everything_the_bands_allow_fails_only_on_the_open_cases() -> None:
    """Pins the spec's sentence: six open calls make wrong a type the bands call acceptable."""
    harmful_open = harmful_table = 0
    for case in ALL.values():
        named = set(everything_the_bands_allow(case)) & set(case.label.wrong)
        if case.set == "open":
            harmful_open += len(named)
        else:
            harmful_table += len(named)

    assert harmful_table == 0
    assert harmful_open == 6


def test_the_bars_are_pooled_so_the_open_set_alone_can_sit_under_them() -> None:
    """Pins the spec's sentence: the plain baseline meets the bars with 17 of 25 on the open set."""
    found = expected = 0
    for case in ALL.values():
        if case.set == "open":
            expected += len(case.label.expected)
            found += len(set(plain_baseline(case)[:5]) & set(case.label.expected))

    assert (found, expected) == (17, 25)
    assert found / expected < BARS_FILE["coverage"]["value"]
