"""The four measures, as `docs/SPEC.md` defines them. Every score is computed here from risk
types: there is no judge, and nothing here knows a threshold except the bars file it is given.

A run is what one pass over the cases returned: for each case the risk types in the order
returned (up to eight), or `None` where the output was dropped by validation or the call failed.
"""

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from domain_health.evals.cases import EvalCase
from domain_health.types import RiskType

SCORED = 5  # coverage, precision and stability look at the first five returned
CaseRun = Sequence[RiskType] | None
Run = Mapping[str, CaseRun]


@dataclass(frozen=True)
class RunScore:
    """One run's counts. The ratios are the run's own."""

    expected: int
    found: int  # expected types among the first five returned
    returned: int  # how many of the first five places were used
    precise: int  # of those, expected or acceptable
    harmful: int  # wrong types anywhere in what was returned, up to eight
    dropped: int  # cases with no usable output

    @property
    def coverage(self) -> float | None:
        return self.found / self.expected if self.expected else None

    @property
    def precision(self) -> float | None:
        return self.precise / self.returned if self.returned else None


def score_run(cases: Mapping[str, EvalCase], run: Run) -> RunScore:
    expected = found = returned = precise = harmful = dropped = 0
    for name, case in cases.items():
        wanted = set(case.label.expected)
        expected += len(wanted)
        everything = run[name]
        if everything is None:
            # Dropped output found nothing. It returned nothing, so it adds nothing to precision.
            dropped += 1
            continue
        scored = set(list(everything)[:SCORED])
        found += len(scored & wanted)
        returned += len(scored)
        precise += len(scored & (wanted | set(case.label.acceptable)))
        harmful += len(set(everything) & set(case.label.wrong))
    return RunScore(expected, found, returned, precise, harmful, dropped)


def stable_cases(cases: Mapping[str, EvalCase], runs: Sequence[Run]) -> int:
    """Cases whose set of first five is the same in every run. Dropped output never matches."""
    stable = 0
    for name in cases:
        answers = [run[name] for run in runs]
        if any(answer is None for answer in answers):
            continue
        firsts = {frozenset(list(answer)[:SCORED]) for answer in answers if answer is not None}
        stable += len(firsts) == 1
    return stable


def _mean(values: Sequence[float | None]) -> float | None:
    """The mean of the runs' ratios; none when any run has no ratio to take."""
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None) / len(values)


@dataclass(frozen=True)
class Measures:
    runs: tuple[RunScore, ...]
    cases: int
    stable: int

    @property
    def coverage(self) -> float | None:
        return _mean([run.coverage for run in self.runs])

    @property
    def precision(self) -> float | None:
        return _mean([run.precision for run in self.runs])

    @property
    def harmful(self) -> int:
        return sum(run.harmful for run in self.runs)

    @property
    def stability(self) -> float | None:
        return self.stable / self.cases if self.cases else None

    @property
    def dropped(self) -> int:
        return sum(run.dropped for run in self.runs)

    @property
    def case_runs(self) -> int:
        return self.cases * len(self.runs)

    def value(self, name: str) -> float | None:
        values: dict[str, float | None] = {
            "coverage": self.coverage,
            "precision": self.precision,
            "harmful": float(self.harmful),
            "stability": self.stability,
        }
        return values[name]


def measure(cases: Mapping[str, EvalCase], runs: Sequence[Run]) -> Measures:
    scores = tuple(score_run(cases, run) for run in runs)
    return Measures(runs=scores, cases=len(cases), stable=stable_cases(cases, runs))


def coverage_by_type(
    cases: Mapping[str, EvalCase], runs: Sequence[Run]
) -> dict[RiskType, tuple[int, int]]:
    """For each risk type: times found in the first five, and times expected, over all runs."""
    counts = {risk: [0, 0] for risk in RiskType}
    for run in runs:
        for name, case in cases.items():
            everything = run[name]
            scored = set() if everything is None else set(list(everything)[:SCORED])
            for risk in case.label.expected:
                counts[risk][1] += 1
                counts[risk][0] += risk in scored
    return {risk: (found, expected) for risk, (found, expected) in counts.items()}


@dataclass(frozen=True)
class Bar:
    op: str
    value: float

    def met_by(self, value: float | None) -> bool:
        """A measure with no value (nothing to take a ratio of) has not met its bar."""
        if value is None:
            return False
        if self.op == ">=":
            return value >= self.value
        if self.op == "==":
            return value == self.value
        raise ValueError(f"a bar with an operator this code does not know: {self.op}")


MEASURES = ("coverage", "precision", "harmful", "stability")


def load_bars(path: Path) -> dict[str, Bar]:
    """The owner's bars. All four must be there; the code holds none of its own."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if sorted(raw) != sorted(MEASURES):
        raise ValueError(f"{path.name} must hold exactly the four bars: {', '.join(MEASURES)}")
    return {
        name: Bar(op=str(raw[name]["op"]), value=float(raw[name]["value"])) for name in MEASURES
    }
