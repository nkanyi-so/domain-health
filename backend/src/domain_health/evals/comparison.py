"""The model against the rules-only baseline on the open cases (docs/SPEC.md, decision 0010).

The table cases cannot tell a model from a table of thresholds. The open cases can, but only
if the comparison cannot itself be passed by a slightly looser table: a test runs every such
table through `better_than_baseline` and requires each to fail.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from domain_health.evals.cases import EvalCase
from domain_health.evals.table import baseline_risks
from domain_health.types import RiskType

# What one run returned: case name to the risk types in the order returned (up to eight).
Run = Mapping[str, Sequence[RiskType]]

SCORED = 5  # coverage and precision look at the first five; harmful at everything returned
PRECISION_BAR = 0.80
MIN_GAIN_PER_RUN = 1  # expected items found beyond the baseline, on average per run
MIN_CASES_GAINED = 2  # in a run that counts, the gain comes from at least this many cases
MIN_RUNS_GAINED = 2  # and that holds in at least this many of the runs


@dataclass(frozen=True)
class OpenScore:
    """One run scored on the open cases."""

    found: int  # expected types among the first five returned
    expected: int
    returned: int  # how many of the first five places were used
    precise: int  # of those, expected or acceptable
    harmful: int  # wrong types anywhere in what was returned
    cases_gained: int  # cases where it found an expected type the baseline missed


def baseline_run(cases: Mapping[str, EvalCase]) -> dict[str, list[RiskType]]:
    return {name: baseline_risks(case.input) for name, case in cases.items()}


def score_open_run(cases: Mapping[str, EvalCase], run: Run, baseline: Run) -> OpenScore:
    found = expected = returned = precise = harmful = cases_gained = 0
    for name, case in cases.items():
        everything = list(run.get(name, ()))
        scored = set(everything[:SCORED])
        wanted = set(case.label.expected)
        expected += len(wanted)
        found += len(scored & wanted)
        returned += len(scored)
        precise += len(scored & (wanted | set(case.label.acceptable)))
        harmful += len(set(everything) & set(case.label.wrong))
        if (scored & wanted) - set(list(baseline.get(name, ()))[:SCORED]):
            cases_gained += 1
    return OpenScore(found, expected, returned, precise, harmful, cases_gained)


def better_than_baseline(open_cases: Mapping[str, EvalCase], runs: Sequence[Run]) -> bool:
    """Whether these runs do better than the rules-only baseline on the open cases.

    All four must hold: no more harmful output than the baseline; precision at its bar; on
    average at least one more expected item per run than the baseline; and in at least two
    runs the gain is real (more found than the baseline) and comes from at least two cases.
    """
    if not runs or any(case.set != "open" for case in open_cases.values()):
        raise ValueError("the comparison needs at least one run, on open cases only")
    baseline = baseline_run(open_cases)
    base = score_open_run(open_cases, baseline, baseline)
    scores = [score_open_run(open_cases, run, baseline) for run in runs]

    returned = sum(score.returned for score in scores)
    no_more_harm = sum(score.harmful for score in scores) <= base.harmful * len(runs)
    precise_enough = returned > 0 and (
        sum(score.precise for score in scores) / returned >= PRECISION_BAR
    )
    gained_enough = sum(score.found for score in scores) >= (base.found + MIN_GAIN_PER_RUN) * len(
        runs
    )
    runs_gained = sum(
        score.found > base.found and score.cases_gained >= MIN_CASES_GAINED for score in scores
    )
    return no_more_harm and precise_enough and gained_enough and runs_gained >= MIN_RUNS_GAINED
