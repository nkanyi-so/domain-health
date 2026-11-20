"""The four measures on plain numbers: small made-up cases whose scores can be worked by hand."""

import pytest

from domain_health.evals.cases import EvalCase, Label, load_cases
from domain_health.evals.scoring import (
    Bar,
    Run,
    coverage_by_type,
    load_bars,
    measure,
    score_run,
    stable_cases,
)
from domain_health.types import RiskType as R
from tests.paths import BARS, CASES

INPUT = load_cases(CASES)["01-healthy-baseline"].input


def case(expected: list[R], acceptable: list[R], wrong: list[R]) -> EvalCase:
    label = Label(expected=expected, acceptable=acceptable, wrong=wrong)
    return EvalCase(set="table", input=INPUT, label=label, note="made up")


CASES_3 = {
    # two expected, one acceptable, one wrong; everything else is noise
    "a": case([R.DMARC_POLICY_NONE, R.DKIM_KEY_1024], [R.SPF_WEAK_ALL], [R.REPUTATION_POOR]),
    # one expected
    "b": case([R.VOLUME_SPIKE], [], [R.NEW_DOMAIN_VOLUME, R.BLOCKLIST_RECENT]),
    # healthy: nothing expected
    "c": case([], [], [R.VOLUME_SPIKE]),
}


def test_one_run_counted_by_hand() -> None:
    run = {
        "a": [R.DMARC_POLICY_NONE, R.SPF_WEAK_ALL, R.ENGAGEMENT_DECLINING],  # 1 found, 2 precise
        "b": [R.VOLUME_SPIKE, R.NEW_DOMAIN_VOLUME],  # 1 found, 1 precise, 1 harmful
        "c": [],  # returns nothing: adds nothing
    }

    score = score_run(CASES_3, run)

    assert (score.expected, score.found) == (3, 2)
    assert (score.returned, score.precise) == (5, 3)
    assert score.harmful == 1
    assert score.dropped == 0
    assert score.coverage == pytest.approx(2 / 3)
    assert score.precision == pytest.approx(3 / 5)


def test_coverage_and_precision_look_at_the_first_five_and_harmful_at_all_eight() -> None:
    padding = [
        R.SPF_NEAR_LOOKUP_LIMIT,
        R.COMPLAINT_RATE_ELEVATED,
        R.BOUNCE_RATE_ELEVATED,
        R.ENGAGEMENT_DECLINING,
        R.REPUTATION_DECLINING,
    ]
    # The expected type is sixth and the wrong type seventh.
    run = {"a": [*padding, R.DMARC_POLICY_NONE, R.REPUTATION_POOR], "b": [], "c": []}

    score = score_run(CASES_3, run)

    assert score.found == 0
    assert (score.returned, score.precise) == (5, 0)
    assert score.harmful == 1


def test_dropped_output_found_nothing_and_adds_nothing_to_precision() -> None:
    run = {"a": None, "b": [R.VOLUME_SPIKE], "c": None}

    score = score_run(CASES_3, run)

    assert (score.expected, score.found) == (3, 1)
    assert (score.returned, score.precise) == (1, 1)
    assert score.dropped == 2
    assert score.harmful == 0


def test_stability_is_about_the_set_of_the_first_five_not_their_order() -> None:
    same_set = [R.DMARC_POLICY_NONE, R.DKIM_KEY_1024]
    runs = [
        {"a": same_set, "b": [R.VOLUME_SPIKE], "c": []},
        {"a": same_set[::-1], "b": [R.VOLUME_SPIKE, R.BLOCKLIST_RECENT], "c": []},
        {"a": same_set, "b": [R.VOLUME_SPIKE], "c": []},
    ]

    assert stable_cases(CASES_3, runs) == 2  # a and c; b changed once


def test_a_change_past_the_fifth_place_does_not_break_stability() -> None:
    five = [
        R.DMARC_POLICY_NONE,
        R.DKIM_KEY_1024,
        R.SPF_WEAK_ALL,
        R.VOLUME_SPIKE,
        R.ENGAGEMENT_DECLINING,
    ]
    runs = [{"a": five, "b": [], "c": []}, {"a": [*five, R.BLOCKLIST_RECENT], "b": [], "c": []}]

    assert stable_cases(CASES_3, runs) == 3


def test_dropped_output_never_matches_even_itself() -> None:
    runs: list[Run] = [{"a": None, "b": [], "c": []}] * 3

    assert stable_cases(CASES_3, runs) == 2


def test_the_measures_are_the_mean_of_the_runs_and_harmful_is_their_sum() -> None:
    runs: list[Run] = [
        {"a": [R.DMARC_POLICY_NONE, R.DKIM_KEY_1024], "b": [R.VOLUME_SPIKE], "c": []},  # 3/3, 3/3
        {"a": [R.DMARC_POLICY_NONE], "b": [R.NEW_DOMAIN_VOLUME], "c": []},  # 1/3, 1/2, 1 harmful
        {"a": [R.REPUTATION_POOR], "b": None, "c": [R.VOLUME_SPIKE]},  # 0/3, 0/2, 2 harmful
    ]

    measures = measure(CASES_3, runs)

    assert measures.coverage == pytest.approx((1 + 1 / 3 + 0) / 3)
    # The mean of each run's ratio, not the pooled 4 of 7.
    assert measures.precision == pytest.approx((1 + 1 / 2 + 0) / 3)
    assert measures.precision != pytest.approx(4 / 7)
    assert measures.harmful == 3
    assert measures.dropped == 1
    assert measures.case_runs == 9
    assert measures.stability == pytest.approx(0 / 3)
    assert [run.harmful for run in measures.runs] == [0, 1, 2]


def test_a_run_that_returns_nothing_at_all_has_no_precision_to_report() -> None:
    measures = measure(CASES_3, [{"a": [], "b": [], "c": []}] * 3)

    assert measures.precision is None
    assert measures.coverage == 0
    assert measures.stability == 1


def test_coverage_for_each_type_counts_every_run() -> None:
    runs: list[Run] = [
        {"a": [R.DMARC_POLICY_NONE, R.DKIM_KEY_1024], "b": [R.VOLUME_SPIKE], "c": []},
        {"a": [R.DMARC_POLICY_NONE], "b": None, "c": []},
    ]

    by_type = coverage_by_type(CASES_3, runs)

    assert by_type[R.DMARC_POLICY_NONE] == (2, 2)
    assert by_type[R.DKIM_KEY_1024] == (1, 2)
    assert by_type[R.VOLUME_SPIKE] == (1, 2)
    assert by_type[R.BLOCKLIST_RECENT] == (0, 0)


def test_a_bar_is_met_or_missed_and_no_value_is_missed() -> None:
    at_least = Bar(op=">=", value=0.8)
    exactly = Bar(op="==", value=0)

    assert at_least.met_by(0.8)
    assert at_least.met_by(1.0)
    assert not at_least.met_by(0.7999)
    assert not at_least.met_by(None)
    assert exactly.met_by(0.0)
    assert not exactly.met_by(1.0)
    with pytest.raises(ValueError, match="operator"):
        Bar(op="<", value=1).met_by(0)


def test_the_bars_come_from_the_owners_file_and_all_four_are_there() -> None:
    bars = load_bars(BARS)

    assert sorted(bars) == ["coverage", "harmful", "precision", "stability"]
    assert all(isinstance(bar.value, float) for bar in bars.values())
