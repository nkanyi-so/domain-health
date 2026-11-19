"""The model against the rules-only baseline on the open cases (docs/SPEC.md, decision 0010).

Reported as evidence, not a bar. The table cases cannot tell a model from a table of
thresholds, and the open cases were meant to. A test shows that no table which also returns the
bands' "acceptable" types passes `better_than_baseline`; a table with one threshold moved still
does (decision 0012), so a pass here is not proof of judgment.
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
RUNS = 3  # every measure is defined over three runs


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


def mean_precision(scores: Sequence[OpenScore]) -> float | None:
    """Precision as the spec defines it: the mean over the runs of each run's own ratio.

    None when a run returned nothing at all: there is no ratio to take.
    """
    if not scores or any(score.returned == 0 for score in scores):
        return None
    return sum(score.precise / score.returned for score in scores) / len(scores)


def better_than_baseline(open_cases: Mapping[str, EvalCase], runs: Sequence[Run]) -> bool:
    """Whether these runs do better than the rules-only baseline on the open cases.

    All four must hold: no more harmful output than the baseline; precision at its bar; on
    average at least one more expected item per run than the baseline; and in at least two
    runs the gain is real (more found than the baseline) and comes from at least two cases.
    """
    if len(runs) != RUNS or any(case.set != "open" for case in open_cases.values()):
        raise ValueError(f"the comparison is defined over {RUNS} runs, on open cases only")
    baseline = baseline_run(open_cases)
    base = score_open_run(open_cases, baseline, baseline)
    scores = [score_open_run(open_cases, run, baseline) for run in runs]

    no_more_harm = sum(score.harmful for score in scores) <= base.harmful * len(runs)
    precision = mean_precision(scores)
    precise_enough = precision is not None and precision >= PRECISION_BAR
    gained_enough = sum(score.found for score in scores) >= (base.found + MIN_GAIN_PER_RUN) * len(
        runs
    )
    runs_gained = sum(
        score.found > base.found and score.cases_gained >= MIN_CASES_GAINED for score in scores
    )
    return no_more_harm and precise_enough and gained_enough and runs_gained >= MIN_RUNS_GAINED
