"""The eval page's bundled numbers are what `make eval-summary` writes today from the results
file, and hold totals only."""

import json
from pathlib import Path
from typing import Any

import pytest

from domain_health.eval_summary import RESULTS, SUMMARY, generate, main, summary
from tests.paths import REPO


def results() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(RESULTS.read_text(encoding="utf-8"))
    return loaded


def test_the_committed_summary_is_current() -> None:
    assert RESULTS == REPO / "evals" / "results.json"
    assert SUMMARY == REPO / "frontend" / "src" / "data" / "eval-summary.json"
    assert SUMMARY.exists(), (
        "frontend/src/data/eval-summary.json is missing: run `make eval-summary`"
    )

    assert SUMMARY.read_text(encoding="utf-8") == generate(), (
        "frontend/src/data/eval-summary.json is out of date with evals/results.json: "
        "run `make eval-summary` and commit the file"
    )


def test_the_numbers_are_the_results_files_own() -> None:
    source, made = results(), summary(results())

    assert made["prompt_version"] == source["prompt_version"]
    assert made["model"] == source["model"]
    assert made["case_runs"] == source["cases"] * source["runs"]
    for name in ("coverage", "precision", "harmful", "stability"):
        assert made["measures"][name]["value"] == source["measures"][name]["value"]
        assert made["measures"][name]["met"] is source["measures"][name]["met"]
        assert made["measures"][name]["bar"] == source["measures"][name]["bar"]
    assert made["all_bars_met"] is source["all_bars_met"]
    for name in ("table", "open"):
        assert made["sets"][name]["harmful"] == source["sets"][name]["harmful"]
        assert made["sets"][name]["baseline_coverage"] == source["sets"][name]["baseline_coverage"]
    assert [entry["prompt_version"] for entry in made["not_in_use"]] == [
        entry["prompt_version"] for entry in source["not_in_use"]
    ]


def test_the_summary_holds_totals_only() -> None:
    """Every value is one number, word or yes/no under a key named in the module: nothing that
    could be a row for a single case."""
    made = summary(results())

    assert sorted(made) == sorted(
        [
            "prompt_version",
            "model",
            "recorded_at",
            "runs",
            "cases",
            "case_runs",
            "dropped",
            "all_bars_met",
            "better_than_baseline_on_open",
            "measures",
            "sets",
            "not_in_use",
            "open_runs",
            "rules_only",
        ]
    )
    groups = [
        *made["measures"].values(),
        *made["sets"].values(),
        *made["not_in_use"],
        *made["open_runs"],
        made["rules_only"],
    ]
    for group in groups:
        for value in group.values():
            assert not isinstance(value, (dict, list))
    assert isinstance(made["cases"], int)


def test_the_totals_scored_here_agree_with_the_results_file() -> None:
    """The open set's counts for each run and the baseline's scores are scored by this module, so
    they are held to what the results file says of the same runs."""
    source, made = results(), summary(results())
    opened, runs = source["sets"]["open"], made["open_runs"]

    assert [row["run"] for row in runs] == list(range(1, source["runs"] + 1))
    assert sorted(runs[0]) == [
        "expected",
        "found",
        "harmful",
        "rules_found",
        "rules_harmful",
        "run",
    ]
    assert {row["expected"] for row in runs} == {opened["expected_items"]}
    assert sum(row["harmful"] for row in runs) == opened["harmful"]
    assert sum(row["found"] / row["expected"] for row in runs) / len(runs) == pytest.approx(
        opened["coverage"]
    )
    for row in runs:
        assert row["rules_found"] / row["expected"] == pytest.approx(opened["baseline_coverage"])
    assert {row["rules_harmful"] for row in runs} == {opened["baseline_harmful"]}
    assert sorted(made["rules_only"]) == [
        "all_bars_met",
        "coverage",
        "harmful",
        "precision",
        "stability",
    ]
    assert isinstance(made["rules_only"]["all_bars_met"], bool)


def test_a_table_where_a_total_should_be_stops_the_build() -> None:
    broken = results()
    broken["sets"]["open"]["harmful"] = [{"case": "one", "harmful": 1}]

    with pytest.raises(ValueError, match="not a single value"):
        summary(broken)


def test_the_command_writes_the_file(tmp_path: Path) -> None:
    target = tmp_path / "data" / "eval-summary.json"

    assert main(target) == 0
    assert target.read_text(encoding="utf-8") == generate()
