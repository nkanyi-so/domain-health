"""Scores the recordings of one prompt version: the results file and the lines `make eval` prints.

Reads committed recordings only; makes no call. The model's numbers stand beside the rules-only
baseline's, for all the cases and for each set. Per-case results of the open set are never
printed or written: only totals.

Two things are shown so a reader can tell a model from a table of thresholds. A type the rubric's
bands call merely acceptable earns nothing on any measure, and on an open case it may be the very
thing the written call makes wrong: how many of those each set got is counted. And the runs are
scored again with only the types the bands expect kept: where that line equals the baseline's,
everything the model added to the table was a type the bands do not expect.
"""

import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path

from domain_health.evals.cases import EvalCase
from domain_health.evals.comparison import baseline_run, better_than_baseline
from domain_health.evals.scoring import (
    MEASURES,
    Bar,
    CaseRun,
    Measures,
    Run,
    coverage_by_type,
    measure,
)
from domain_health.evals.table import table_label
from domain_health.models import Frozen
from domain_health.risks.model import (
    ModelCall,
    RecordedRiskModel,
    RisksUnavailableError,
    load_calls,
    risks_from,
)
from domain_health.risks.prompt import Prompt
from domain_health.risks.prompt_rules import relative_wording

RUNS = 3


class NoRecordingsError(Exception):
    """The recordings for this prompt version and model do not cover the cases."""


def run_folder(recordings: Path, prompt_version: str, model: str, run: int) -> Path:
    return recordings / prompt_version / model / f"run-{run}"


def load_runs(
    cases: Mapping[str, EvalCase], prompt: Prompt, model: str, recordings: Path
) -> tuple[list[Run], list[ModelCall], dict[str, list[str]]]:
    """The three recorded runs as scored input, the calls behind them, and for each case the
    reasons its output was dropped. Raises if any case has no recording in any run."""
    runs: list[Run] = []
    calls: list[ModelCall] = []
    drops: dict[str, list[str]] = {}
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        recorded = RecordedRiskModel(prompt, model, load_calls(folder) if folder.is_dir() else [])
        run: dict[str, CaseRun] = {}
        missing = 0
        for name, case in cases.items():
            call = recorded.recorded(case.input)
            if call is None:
                missing += 1
                continue
            calls.append(call)
            try:
                run[name] = [risk.type for risk in risks_from(case.input, call)]
            except RisksUnavailableError as error:
                run[name] = None
                drops.setdefault(name, []).append(f"run {number}: {error}")
        if missing:
            raise NoRecordingsError(
                f"run {number} of {prompt.version} on {model} has no recording for {missing} of "
                f"{len(cases)} cases (or they were recorded with another text of this prompt)"
            )
        runs.append(run)
    return runs, calls, drops


class MeasureResult(Frozen):
    value: float | None
    runs: list[float | None]
    bar: str
    met: bool


class SetResult(Frozen):
    """One set of cases: the model's numbers and, beside them, the rules-only baseline's."""

    cases: int
    expected_items: int
    coverage: float | None
    precision: float | None
    harmful: int
    stability: float | None
    dropped: int
    baseline_coverage: float | None
    baseline_precision: float | None
    baseline_harmful: int
    # Types returned that the rubric's bands call merely acceptable, over the runs.
    band_acceptable_returned: int
    # Types returned that the rubric's bands call wrong for that input, over the runs. On the
    # table set this is the harmful count; on the open set a written call can differ.
    band_wrong_returned: int
    # The same runs with only the types the bands expect kept.
    expected_only_coverage: float | None
    expected_only_precision: float | None
    expected_only_harmful: int
    expected_only_stability: float | None


class OtherVersion(Frozen):
    """A prompt version recorded on the same model that is not the one in use: its four scores."""

    prompt_version: str
    coverage: float | None
    precision: float | None
    harmful: int
    stability: float | None


def other_version(
    cases: Mapping[str, EvalCase], prompt: Prompt, runs: Sequence[Run]
) -> OtherVersion:
    scored = measure(cases, runs)
    return OtherVersion(
        prompt_version=prompt.version,
        coverage=scored.coverage,
        precision=scored.precision,
        harmful=scored.harmful,
        stability=scored.stability,
    )


class Results(Frozen):
    prompt_version: str
    prompt_sha256: str
    model: str
    reasoning_effort: str
    temperature: float | None
    recorded_at: str
    runs: int
    cases: int
    case_runs: int
    measures: dict[str, MeasureResult]
    all_bars_met: bool
    dropped: int
    sets: dict[str, SetResult]
    coverage_by_type: dict[str, str]
    better_than_baseline_on_open: bool
    # Sentences of the prompt that place a line relative to a figure: shown, not judged.
    prompt_relative_wording: list[str]
    # Other versions recorded on this model, newest last: reported, never the ones in use.
    not_in_use: list[OtherVersion]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    median_latency_ms: int


def _kept(run: Run, cases: Mapping[str, EvalCase], band: str) -> dict[str, CaseRun]:
    """One run with only the types kept that the rubric's bands put in `band` for that input."""
    kept: dict[str, CaseRun] = {}
    for name, case in cases.items():
        returned = run[name]
        wanted = getattr(table_label(case.input), band)
        kept[name] = None if returned is None else [risk for risk in returned if risk in wanted]
    return kept


def _set_result(cases: Mapping[str, EvalCase], runs: Sequence[Run]) -> SetResult:
    chosen = [{name: run[name] for name in cases} for run in runs]
    model = measure(cases, chosen)
    baseline = measure(cases, [baseline_run(cases)] * len(runs))
    acceptable = [_kept(run, cases, "acceptable") for run in chosen]
    wrong = [_kept(run, cases, "wrong") for run in chosen]
    expected_only = measure(cases, [_kept(run, cases, "expected") for run in chosen])
    return SetResult(
        cases=len(cases),
        expected_items=model.runs[0].expected,
        coverage=model.coverage,
        precision=model.precision,
        harmful=model.harmful,
        stability=model.stability,
        dropped=model.dropped,
        baseline_coverage=baseline.coverage,
        baseline_precision=baseline.precision,
        baseline_harmful=baseline.harmful,
        band_acceptable_returned=sum(
            len(kept or ()) for run in acceptable for kept in run.values()
        ),
        band_wrong_returned=sum(len(kept or ()) for run in wrong for kept in run.values()),
        expected_only_coverage=expected_only.coverage,
        expected_only_precision=expected_only.precision,
        expected_only_harmful=expected_only.harmful,
        expected_only_stability=expected_only.stability,
    )


def _per_run(measures: Measures, name: str) -> list[float | None]:
    if name == "coverage":
        return [run.coverage for run in measures.runs]
    if name == "precision":
        return [run.precision for run in measures.runs]
    if name == "harmful":
        return [float(run.harmful) for run in measures.runs]
    return []  # stability is one number over the runs together


def results_for(
    cases: Mapping[str, EvalCase],
    prompt: Prompt,
    model: str,
    runs: Sequence[Run],
    calls: Sequence[ModelCall],
    bars: Mapping[str, Bar],
    not_in_use: Sequence[OtherVersion] = (),
) -> Results:
    everything = measure(cases, runs)
    table = {name: case for name, case in cases.items() if case.set == "table"}
    opened = {name: case for name, case in cases.items() if case.set == "open"}
    measures = {
        name: MeasureResult(
            value=everything.value(name),
            runs=_per_run(everything, name),
            bar=f"{bars[name].op} {bars[name].value:g}",
            met=bars[name].met_by(everything.value(name)),
        )
        for name in MEASURES
    }
    # The comparison scores a dropped output as one that returned nothing.
    open_runs = [{name: list(run[name] or []) for name in opened} for run in runs]
    by_type = coverage_by_type(cases, runs)
    return Results(
        prompt_version=prompt.version,
        prompt_sha256=prompt.sha256,
        model=model,
        reasoning_effort=calls[0].reasoning_effort,
        temperature=calls[0].temperature,
        recorded_at=max(call.recorded_at for call in calls),
        runs=len(runs),
        cases=len(cases),
        case_runs=everything.case_runs,
        measures=measures,
        all_bars_met=all(result.met for result in measures.values()),
        dropped=everything.dropped,
        sets={"table": _set_result(table, runs), "open": _set_result(opened, runs)},
        coverage_by_type={
            risk.value: f"{found}/{expected}" for risk, (found, expected) in by_type.items()
        },
        better_than_baseline_on_open=better_than_baseline(opened, open_runs),
        prompt_relative_wording=relative_wording(prompt.text),
        not_in_use=list(not_in_use),
        input_tokens=sum(call.input_tokens for call in calls),
        output_tokens=sum(call.output_tokens for call in calls),
        cost_usd=round(sum(call.cost_usd for call in calls), 6),
        median_latency_ms=int(statistics.median(call.latency_ms for call in calls)),
    )


def _number(value: float | None) -> str:
    return "none" if value is None else f"{value:.3f}"


def lines(results: Results) -> list[str]:
    """What `make eval` prints: one line per measure with its bar, then what has no bar."""
    temperature = "not set" if results.temperature is None else f"{results.temperature:g}"
    out = [
        f"{results.prompt_version} ({results.prompt_sha256[:12]}) on {results.model}, "
        f"reasoning {results.reasoning_effort}, temperature {temperature}: "
        f"{results.runs} runs of {results.cases} cases, recorded {results.recorded_at[:10]}",
    ]
    for name in MEASURES:
        result = results.measures[name]
        if name == "harmful":
            shown = f"{int(result.value or 0)} in {results.case_runs} case-runs"
            if not result.value:
                # Runs that agree are not separate evidence: say how many cases gave the same
                # first five every time (stability's count; places six to eight may differ).
                agreed = round((results.measures["stability"].value or 0) * results.cases)
                shown += (
                    f" ({results.cases} cases, {results.runs} runs whose first five agreed "
                    f"on {agreed})"
                )
        elif name == "stability":
            stable = round((result.value or 0) * results.cases)
            shown = f"{_number(result.value)} ({stable} of {results.cases} cases)"
        else:
            shown = _number(result.value)
        each = ""
        if result.runs:
            per_run = " ".join(
                f"{int(v)}" if name == "harmful" and v is not None else _number(v)
                for v in result.runs
            )
            each = f"  each run: {per_run}"
        verdict = "met" if result.met else "missed"
        out.append(f"{name:<10} {shown:<28} bar {result.bar:<8} {verdict}{each}")
    out.append(f"dropped    {results.dropped} of {results.case_runs} outputs")
    out.append("no bar:")
    for name, part in results.sets.items():
        out.append(
            f"  {name} set ({part.cases} cases, {part.expected_items} expected items): "
            f"coverage {_number(part.coverage)}, precision {_number(part.precision)}, "
            f"harmful {part.harmful}, stability {_number(part.stability)}, "
            f"dropped {part.dropped} | rules-only baseline: "
            f"coverage {_number(part.baseline_coverage)}, "
            f"precision {_number(part.baseline_precision)}, harmful {part.baseline_harmful}"
        )
        out.append(
            f"    types returned that the bands call merely acceptable: "
            f"{part.band_acceptable_returned}, wrong: {part.band_wrong_returned} | "
            f"with only the types the bands expect kept: "
            f"coverage {_number(part.expected_only_coverage)}, "
            f"precision {_number(part.expected_only_precision)}, "
            f"harmful {part.expected_only_harmful}, "
            f"stability {_number(part.expected_only_stability)}"
        )
    by_type = ", ".join(f"{risk} {count}" for risk, count in results.coverage_by_type.items())
    out.append(f"  coverage by risk type (found/expected over the runs): {by_type}")
    better = "yes" if results.better_than_baseline_on_open else "no"
    out.append(f"  better than the rules-only baseline on the open set: {better}")
    out.append(
        f"  prompt sentences that place a line relative to a figure, a field's name or a "
        f"span of time (listed in the results file): {len(results.prompt_relative_wording)}"
    )
    for other in results.not_in_use:
        out.append(
            f"  not in use, recorded on the same model: {other.prompt_version}: "
            f"coverage {_number(other.coverage)}, precision {_number(other.precision)}, "
            f"harmful {other.harmful} in {results.case_runs}, "
            f"stability {_number(other.stability)}"
        )
    out.append(
        f"  cost ${results.cost_usd:.4f}, {results.input_tokens} tokens in, "
        f"{results.output_tokens} out, median latency {results.median_latency_ms} ms"
    )
    return out


def table_report(
    cases: Mapping[str, EvalCase], runs: Sequence[Run], drops: Mapping[str, Sequence[str]]
) -> list[str]:
    """Per-case results for the table set only: what prompt changes are argued from. The open
    set's cases never appear here. A type returned that the label calls merely acceptable is
    shown too: it costs nothing here and earns nothing, and a prompt writer has to see it."""
    out: list[str] = []
    for name, case in cases.items():
        if case.set != "table":
            continue
        problems: list[str] = list(drops.get(name, []))
        for number, run in enumerate(runs, start=1):
            returned = run[name]
            if returned is None:
                continue
            first = list(returned)[:5]
            missed = [risk.value for risk in case.label.expected if risk not in first]
            wrong = [risk.value for risk in returned if risk in case.label.wrong]
            allowed = set(case.label.expected) | set(case.label.acceptable)
            noise = [risk.value for risk in first if risk not in allowed | set(case.label.wrong)]
            acceptable = [risk.value for risk in returned if risk in case.label.acceptable]
            found_all = (
                ("missed", missed),
                ("wrong", wrong),
                ("noise", noise),
                ("acceptable, not expected", acceptable),
            )
            for label, found in found_all:
                if found:
                    problems.append(f"run {number}: {label} {', '.join(found)}")
        out.append(f"{name}: {'; '.join(problems) if problems else 'only what is expected'}")
    return out
