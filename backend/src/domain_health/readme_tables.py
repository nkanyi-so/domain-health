"""`make readme`: the parts of `README.md` that are numbers, written from the files that hold them.

The README's eval tables may not be typed by hand. Each generated part sits between two HTML
comments, `<!-- name:start -->` and `<!-- name:end -->`, and this command rewrites what is between
them. A backend test fails when the README and what this module makes differ.

Where each part comes from:

- `eval-table`, `eval-sets`, `prompt-wording`, `v4-boundaries`, `v4-wording`: `evals/results.json`,
  the file `make eval` writes. Two totals that file does not hold (the rules-only baseline's four
  scores over all the cases, and each run's counts on the open set) are scored by the eval
  summary's own code, as they are for the page.
- `eval-attempts`: every prompt version and model that has committed recordings, scored again
  with the harness, and the cost of each from the spend ledger.
- `build-numbers`: `docs/RUN_LOG.md`, counted by phase.

Totals only: no eval case is named or printed. Free, and it reaches nothing outside this
repository. The deployed service never imports this module.
"""

import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from domain_health.eval_summary import summary
from domain_health.evals.cases import load_cases
from domain_health.evals.report import load_runs
from domain_health.evals.scoring import MEASURES, Bar, load_bars, measure
from domain_health.risks.prompt import load_prompt, prompt_versions
from domain_health.seeded.recordings import REPO

README = REPO / "README.md"
RESULTS = REPO / "evals" / "results.json"
RUN_LOG = REPO / "docs" / "RUN_LOG.md"
LEDGER = REPO / "evals" / "ledger.jsonl"

# The phases whose rows are finished. Phase 6 writes the README, so its own row would change
# under it: it is left out, and the README says so.
FINISHED_PHASES = (0, 1, 2, 3, 4, 5)

# Version 4's wording, boundary by boundary, as `docs/DECISIONS_TO_REVIEW.md` lists it: the risk
# type, the rubric's line it pins, and a few words from each sentence that does the pinning. The
# sentences themselves are taken from the results file's `not_in_use` list.
BOUNDARIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "`dmarc_policy_none`",
        "the rubric's 90 days",
        (
            "gives its length in days",
            "is less than the length of the lookback window in days",
            "at least as old as the lookback window is long",
        ),
    ),
    (
        "`blocklist_recent`",
        "the rubric's 30 days",
        (
            "exactly a third of the lookback window",
            "A value equal to that count is",
            "that exact count of days still fits",
        ),
    ),
    (
        "`new_domain_volume`",
        "the rubric's 30 days and its volume line",
        (
            "has reached a month or more",
            "equals the bulk-sender count or is below it",
            "is above the bulk-sender count",
        ),
    ),
    (
        "`volume_spike`",
        "the rubric's 365 days",
        ("the number of days in an ordinary year", "is less than a full year old"),
    ),
    (
        "the low-volume line of `complaint_rate_elevated`, `bounce_rate_elevated` and "
        "`engagement_declining`",
        "the rubric's 1,000 messages a week",
        (
            "it has not reached the thousands",
            "not raised, whatever the rate is",
            "not raised, however far the rate fell",
        ),
    ),
)


class ReadmeError(Exception):
    """The README or a file it is written from is not in the shape this command expects."""


def _three(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _bar(text: str) -> Bar:
    """A bar as the results file writes it: `>= 0.8` or `== 0`."""
    op, _, number = text.partition(" ")
    return Bar(op=op, value=float(number))


def _bar_words(bar: Bar) -> str:
    if bar.op == ">=":
        return f"at least {bar.value:.2f}"
    if bar.op == "==":
        return f"exactly {bar.value:g}"
    raise ReadmeError(f"a bar with an operator this code does not know: {bar.op}")


def _cell(text: str, met: bool) -> str:
    return f"{text}, met" if met else f"**{text}, missed**"


def _row(
    who: str, values: Mapping[str, float], bars: Mapping[str, Bar], cases: int, case_runs: int
) -> str:
    """One line of the eval table: who, the four measures with met or missed, and the verdict."""
    stable = round(values["stability"] * cases)
    harmful = int(values["harmful"])
    runs = case_runs // cases
    harmful_text = f"{harmful} in {case_runs} case-runs"
    if harmful == 0:
        # The spec's wording for a zero: it bounds a rate, and runs that agree are one sample.
        harmful_text += f" ({cases} cases, {runs} runs whose first five agreed on {stable})"
    texts = {
        "coverage": _three(values["coverage"]),
        "precision": _three(values["precision"]),
        "harmful": harmful_text,
        "stability": f"{_three(values['stability'])} ({stable} of {cases} cases)",
    }
    met = {name: bars[name].met_by(values[name]) for name in MEASURES}
    missed = [name for name in MEASURES if not met[name]]
    verdict = "yes" if not missed else f"**no: {' and '.join(missed)} missed**"
    cells = [_cell(texts[name], met[name]) for name in MEASURES]
    return f"| {who} | {' | '.join(cells)} | {verdict} |"


def eval_table(results: Mapping[str, Any], rules_only: Mapping[str, Any]) -> str:
    """The prompt in use, the rules-only baseline beside it, and every version not in use."""
    bars = {name: _bar(results["measures"][name]["bar"]) for name in MEASURES}
    cases, case_runs = int(results["cases"]), int(results["case_runs"])
    in_use = {name: float(results["measures"][name]["value"]) for name in MEASURES}
    for name in MEASURES:
        if bars[name].met_by(in_use[name]) is not results["measures"][name]["met"]:
            raise ReadmeError(f"the results file's own `met` for {name} disagrees with its bar")
    version, model = results["prompt_version"], results["model"]
    head = " | ".join(f"{name} (bar: {_bar_words(bars[name])})" for name in MEASURES)
    rows = [
        f"Prompt in use: `{version}` (sha256 `{str(results['prompt_sha256'])[:12]}`). "
        f"Model: `{model}`, reasoning effort `{results['reasoning_effort']}`, "
        f"temperature {results['temperature']:g}. "
        f"Run recorded {str(results['recorded_at'])[:10]}: {results['runs']} runs of {cases} "
        f"cases, {case_runs} case-runs. "
        f"Outputs dropped by validation: {results['dropped']} of {case_runs}.",
        "",
        f"| | {head} | All four bars met |",
        "|---|---|---|---|---|---|",
        _row(f"Model, prompt in use: `{version}`", in_use, bars, cases, case_runs),
        _row(
            "Rules-only baseline: the rubric's bands as code, no model",
            {name: float(rules_only[name]) for name in MEASURES},
            bars,
            cases,
            case_runs,
        ),
    ]
    for other in results["not_in_use"]:
        values = {name: float(other[name]) for name in MEASURES}
        who = f"Model, not in use: `{other['prompt_version']}`, same model"
        rows.append(_row(who, values, bars, cases, case_runs))
    return "\n".join(rows)


def _set_rows(name: str, one: Mapping[str, Any], version: str) -> list[str]:
    label = f"{name} ({one['cases']} cases, {one['expected_items']} expected risks)"
    model = [one["coverage"], one["precision"]]
    baseline = [one["baseline_coverage"], one["baseline_precision"]]
    kept = [one["expected_only_coverage"], one["expected_only_precision"]]
    return [
        f"| {label} | model, `{version}` | {_three(model[0])} | {_three(model[1])} "
        f"| {one['harmful']} | {_three(one['stability'])} |",
        f"| | rules-only baseline | {_three(baseline[0])} | {_three(baseline[1])} "
        f"| {one['baseline_harmful']} | not in the results file |",
        f"| | model, only the types the bands expect kept | {_three(kept[0])} | {_three(kept[1])} "
        f"| {one['expected_only_harmful']} | {_three(one['expected_only_stability'])} |",
    ]


def _listed(values: Sequence[object]) -> str:
    words = [str(value) for value in values]
    return words[0] if len(set(words)) == 1 else ", ".join(words[:-1]) + f" and {words[-1]}"


def eval_sets(results: Mapping[str, Any], open_runs: Sequence[Mapping[str, Any]]) -> str:
    """Each set by itself, with no bar: the model, the baseline, and the model's list with only
    the bands' expected types kept; then the counts the README's limits quote."""
    table, opened = results["sets"]["table"], results["sets"]["open"]
    version = str(results["prompt_version"])
    expected = _listed([run["expected"] for run in open_runs])
    by_type = ", ".join(f"`{name}` {found}" for name, found in results["coverage_by_type"].items())
    better = "yes" if results["better_than_baseline_on_open"] else "no"
    return "\n".join(
        [
            "| Set | Who | coverage | precision | harmful answers | stability |",
            "|---|---|---|---|---|---|",
            *_set_rows("table", table, version),
            *_set_rows("open", opened, version),
            "",
            f"- Types `{version}` returned that the rubric's bands call merely acceptable, over "
            f"the {results['runs']} runs: {table['band_acceptable_returned']} on the table set "
            f"and {opened['band_acceptable_returned']} on the open set. Types it returned that "
            f"the bands call wrong: {table['band_wrong_returned']} and "
            f"{opened['band_wrong_returned']}.",
            f"- The open set, run by run: the model found "
            f"{_listed([run['found'] for run in open_runs])} of {expected} expected risks in "
            f"each of the {len(open_runs)} runs, the rules-only baseline "
            f"{_listed([run['rules_found'] for run in open_runs])}. Harmful answers per run: "
            f"the model {_listed([run['harmful'] for run in open_runs])}, the baseline "
            f"{_listed([run['rules_harmful'] for run in open_runs])}.",
            f"- Better than the rules-only baseline on the open set, by the four-part rule in "
            f"`docs/SPEC.md`: **{better}**.",
            f"- Coverage by risk type, found/expected over the {results['runs']} runs: {by_type}.",
        ]
    )


def _details(summary_line: str, sentences: Sequence[str]) -> str:
    return "\n".join(
        [
            "<details>",
            f"<summary>{summary_line}</summary>",
            "",
            *(f"- {sentence}" for sentence in sentences),
            "",
            "</details>",
        ]
    )


def prompt_wording(results: Mapping[str, Any]) -> str:
    """The sentences of the prompt in use that place a line relative to a figure."""
    sentences = results["prompt_relative_wording"]
    return _details(
        f"The {len(sentences)} sentences of <code>{results['prompt_version']}</code> that the "
        "results file lists",
        sentences,
    )


def _not_in_use(results: Mapping[str, Any], version: str) -> Mapping[str, Any]:
    for other in results["not_in_use"]:
        if other["prompt_version"] == version:
            found: Mapping[str, Any] = other
            return found
    raise ReadmeError(f"the results file holds no version not in use named {version}")


def v4_wording(results: Mapping[str, Any]) -> str:
    sentences = _not_in_use(results, "risks-v4")["prompt_relative_wording"]
    return _details(
        f"All {len(sentences)} sentences of <code>risks-v4</code> that the results file lists "
        "under <code>not_in_use</code>",
        sentences,
    )


def v4_boundaries(results: Mapping[str, Any]) -> str:
    """Each boundary version 4 pins, with the sentences that pin it, from the results file."""
    sentences: list[str] = _not_in_use(results, "risks-v4")["prompt_relative_wording"]
    lines: list[str] = []
    for subject, line, markers in BOUNDARIES:
        lines.append(f"- {subject}, {line}:")
        for marker in markers:
            matches = [sentence for sentence in sentences if marker in sentence]
            if len(matches) != 1:
                raise ReadmeError(
                    f"{len(matches)} sentences of risks-v4 in the results file hold {marker!r}"
                )
            lines.append(f"  - {matches[0]}")
    return "\n".join(lines)


def _ledger(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def attempts() -> list[dict[str, Any]]:
    """Every prompt version and model with committed recordings, scored again by the harness, in
    the order they were run: by version, and the first model before the second."""
    evals = REPO / "evals"
    cases = load_cases(evals / "cases")
    bars = load_bars(evals / "bars.toml")
    ledger = _ledger(LEDGER)
    rows: list[dict[str, Any]] = []
    for path in prompt_versions(REPO / "prompts"):
        prompt = load_prompt(path)
        folder = evals / "recordings" / prompt.version
        models = sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []
        for model in models:
            runs, _, _ = load_runs(cases, prompt, model, evals / "recordings")
            scored = measure(cases, runs)
            paid = [
                entry
                for entry in ledger
                if entry["purpose"] == f"eval {prompt.version}" and entry["model"] == model
            ]
            rows.append(
                {
                    "prompt": prompt.version,
                    "model": model,
                    "coverage": scored.coverage,
                    "precision": scored.precision,
                    "harmful": scored.harmful,
                    "stability": scored.stability,
                    "stable": scored.stable,
                    "cases": scored.cases,
                    "case_runs": scored.case_runs,
                    "dropped": scored.dropped,
                    "missed": [
                        name for name in MEASURES if not bars[name].met_by(scored.value(name))
                    ],
                    "calls": len(paid),
                    "cost_usd": sum(float(entry["cost_usd"]) for entry in paid),
                    "day": min((str(entry["at"])[:10] for entry in paid), default="not paid"),
                }
            )
    return rows


def eval_attempts(rows: Sequence[Mapping[str, Any]]) -> str:
    case_runs = _listed([row["case_runs"] for row in rows])
    lines = [
        f"| Attempt | Prompt | Model | Run on | coverage | precision "
        f"| harmful answers (of {case_runs} case-runs) | stability | dropped | Bars missed "
        f"| Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for number, row in enumerate(rows, start=1):
        missed = ", ".join(row["missed"]) if row["missed"] else "none"
        lines.append(
            f"| {number} | `{row['prompt']}` | `{row['model']}` | {row['day']} "
            f"| {_three(row['coverage'])} | {_three(row['precision'])} | {row['harmful']} "
            f"| {_three(row['stability'])} ({row['stable']} of {row['cases']} cases) "
            f"| {row['dropped']} | {missed} | ${row['cost_usd']:.4f} |"
        )
    return "\n".join(lines)


EVENTS = ("review", "verify", "challenge", "stop-opened", "gate-refused")
_MERGED_BY = re.compile(r"merged by \S+")


def run_log_counts(text: str) -> dict[int, dict[str, Any]]:
    """The run log's events for each finished phase: how many of each, and who merged it."""
    counts: dict[int, dict[str, Any]] = {
        phase: {**dict.fromkeys(EVENTS, 0), "merged": ""} for phase in FINISHED_PHASES
    }
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 5 or not parts[1].isdigit() or int(parts[1]) not in counts:
            continue
        phase, event, detail = int(parts[1]), parts[2], parts[3]
        if event in EVENTS:
            counts[phase][event] += 1
        elif event == "gate-merged":
            counts[phase]["merged"] = "the merge gate"
        elif event == "merged" and _MERGED_BY.search(detail):
            counts[phase]["merged"] = "the owner"
    return counts


def build_numbers(text: str) -> str:
    counts = run_log_counts(text)
    lines = [
        "| Phase | Reviewer runs | Verifier runs | Challenger runs | Stops for the owner "
        "| Merge-gate refusals | Merged by |",
        "|---|---|---|---|---|---|---|",
    ]
    for phase, row in counts.items():
        if not row["merged"]:
            raise ReadmeError(f"the run log does not say who merged phase {phase}")
        cells = " | ".join(str(row[event]) for event in EVENTS)
        lines.append(f"| {phase} | {cells} | {row['merged']} |")
    totals = " | ".join(str(sum(row[event] for row in counts.values())) for event in EVENTS)
    by_gate = sum(row["merged"] == "the merge gate" for row in counts.values())
    by_owner = sum(row["merged"] == "the owner" for row in counts.values())
    lines.append(
        f"| **Phases 0 to 5** | {totals} | the merge gate {by_gate}, the owner {by_owner} |"
    )
    return "\n".join(lines)


def blocks() -> dict[str, str]:
    """Every generated part of the README, by its marker's name."""
    results: dict[str, Any] = json.loads(RESULTS.read_text(encoding="utf-8"))
    scored = summary(results)
    return {
        "eval-table": eval_table(results, scored["rules_only"]),
        "eval-sets": eval_sets(results, scored["open_runs"]),
        "eval-attempts": eval_attempts(attempts()),
        "prompt-wording": prompt_wording(results),
        "v4-boundaries": v4_boundaries(results),
        "v4-wording": v4_wording(results),
        "build-numbers": build_numbers(RUN_LOG.read_text(encoding="utf-8")),
    }


def in_readme(text: str, name: str) -> str:
    """What the README holds between one pair of markers. Each pair must be there exactly once."""
    found = re.findall(
        rf"<!-- {re.escape(name)}:start -->\n(.*?)\n<!-- {re.escape(name)}:end -->",
        text,
        re.DOTALL,
    )
    if len(found) != 1:
        raise ReadmeError(f"the README holds the markers for `{name}` {len(found)} times, not once")
    return str(found[0])


def render(text: str, parts: Mapping[str, str]) -> str:
    """The README with every generated part written in again."""
    for name, part in parts.items():
        old = in_readme(text, name)
        start, end = f"<!-- {name}:start -->\n", f"\n<!-- {name}:end -->"
        text = text.replace(start + old + end, start + part + end)
    return text


def main(path: Path = README) -> int:
    before = path.read_text(encoding="utf-8")
    after = render(before, blocks())
    path.write_text(after, encoding="utf-8")
    print(f"{path.name}: {'rewritten' if after != before else 'already current'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
