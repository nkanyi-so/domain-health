"""`make eval-summary`: the part of the eval result the frontend's eval page shows.

The page may not read a file outside `frontend/` when it runs, and its numbers may not be typed
by hand, so this copies them out of `evals/results.json`, the file `make eval` writes, into
`frontend/src/data/eval-summary.json`. Only totals are copied: the measures with their bars, each
set's totals beside the rules-only baseline, the counts, the prompt version and the model. Every
key is named here, so nothing about a single case can ride along.

Two totals the results file does not hold are scored here from the same cases, recordings and
bars, with the harness's own functions: each run's counts on the open set beside the rules-only
baseline's, and the baseline's four scores over all the cases. The sentence beside the claim
quotes them, and a frontend test holds it to them.

Free, and it reaches nothing outside this repository. The deployed service never imports this
module.
"""

import json
import sys
from pathlib import Path
from typing import Any

from domain_health.evals.cases import load_cases
from domain_health.evals.comparison import baseline_run
from domain_health.evals.report import load_runs
from domain_health.evals.scoring import load_bars, measure, score_run
from domain_health.risks.prompt import load_prompt
from domain_health.seeded.fallback import as_text
from domain_health.seeded.recordings import REPO

RESULTS = REPO / "evals" / "results.json"
SUMMARY = REPO / "frontend" / "src" / "data" / "eval-summary.json"

TOP = (
    "prompt_version",
    "model",
    "recorded_at",
    "runs",
    "cases",
    "case_runs",
    "dropped",
    "all_bars_met",
    "better_than_baseline_on_open",
)
MEASURES = ("coverage", "precision", "harmful", "stability")
MEASURE_KEYS = ("value", "bar", "met")
SETS = ("table", "open")
SET_KEYS = (
    "cases",
    "expected_items",
    "coverage",
    "precision",
    "harmful",
    "stability",
    "baseline_coverage",
    "baseline_precision",
    "baseline_harmful",
)
NOT_IN_USE_KEYS = ("prompt_version", "coverage", "precision", "harmful", "stability")


def _plain(value: object, where: str) -> object:
    """A number, a word or a yes/no: never a list or a table, so no row of cases gets through."""
    if isinstance(value, (dict, list)):
        raise ValueError(f"{where} is not a single value")
    return value


def _pick(source: dict[str, Any], keys: tuple[str, ...], where: str) -> dict[str, object]:
    return {key: _plain(source[key], f"{where}.{key}") for key in keys}


def _scored_here(results: dict[str, Any]) -> dict[str, Any]:
    """Each run's counts on the open set beside the rules-only baseline's, and the baseline's
    four scores over all the cases with whether they meet the bars. Counts over a whole set
    only: no case is named."""
    evals = REPO / "evals"
    cases = load_cases(evals / "cases")
    prompt = load_prompt(REPO / "prompts" / f"{results['prompt_version']}.md")
    runs, _, _ = load_runs(cases, prompt, str(results["model"]), evals / "recordings")
    opened = {name: case for name, case in cases.items() if case.set == "open"}
    rules_open = score_run(opened, baseline_run(opened))
    open_runs = []
    for number, run in enumerate(runs, start=1):
        scored = score_run(opened, {name: run[name] for name in opened})
        open_runs.append(
            {
                "run": number,
                "expected": scored.expected,
                "found": scored.found,
                "harmful": scored.harmful,
                "rules_found": rules_open.found,
                "rules_harmful": rules_open.harmful,
            }
        )
    rules = measure(cases, [baseline_run(cases)] * len(runs))
    bars = load_bars(evals / "bars.toml")
    rules_only: dict[str, object] = {name: rules.value(name) for name in MEASURES}
    rules_only["all_bars_met"] = all(bars[name].met_by(rules.value(name)) for name in MEASURES)
    return {"open_runs": open_runs, "rules_only": rules_only}


def summary(results: dict[str, Any]) -> dict[str, Any]:
    """The totals the page shows, and nothing else. A missing key stops the build."""
    return {
        **_scored_here(results),
        **_pick(results, TOP, "results"),
        "measures": {
            name: _pick(results["measures"][name], MEASURE_KEYS, f"measures.{name}")
            for name in MEASURES
        },
        "sets": {name: _pick(results["sets"][name], SET_KEYS, f"sets.{name}") for name in SETS},
        "not_in_use": [
            _pick(entry, NOT_IN_USE_KEYS, "not_in_use") for entry in results["not_in_use"]
        ],
    }


def generate(results: Path = RESULTS) -> str:
    return as_text(summary(json.loads(results.read_text(encoding="utf-8"))))


def main(path: Path = SUMMARY) -> int:
    text = generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.name}: {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
