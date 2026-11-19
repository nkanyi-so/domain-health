"""The eval plumbing end to end on fixture recordings: cases load, the scorer runs, the results
file is written. No threshold is asserted here: whether a bar is met is read at the phase gate."""

import json
from pathlib import Path

import pytest

from domain_health.evals.__main__ import main
from domain_health.evals.cases import load_cases
from domain_health.evals.report import (
    NoRecordingsError,
    lines,
    load_runs,
    results_for,
    run_folder,
    table_report,
)
from domain_health.evals.scoring import load_bars
from domain_health.types import RiskType
from tests.eval_fixtures import (
    MODEL,
    output_text,
    put_call,
    record_as_labelled,
    recorded_call,
    write_prompt,
)
from tests.paths import BARS, CASES, EVALS

ALL = load_cases(CASES)
TABLE_CASE = "06-dmarc-none-established"


def test_recordings_that_match_every_label_score_full_marks(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(tmp_path / "recordings", prompt, ALL)

    runs, calls, drops = load_runs(ALL, prompt, MODEL, tmp_path / "recordings")
    results = results_for(ALL, prompt, MODEL, runs, calls, load_bars(BARS))

    assert (results.runs, results.cases, results.case_runs) == (3, 48, 144)
    assert results.measures["coverage"].value == 1
    assert results.measures["precision"].value == 1
    assert results.measures["harmful"].value == 0
    assert results.measures["stability"].value == 1
    assert results.dropped == 0
    assert drops == {}
    assert len(calls) == 144
    assert (results.sets["table"].cases, results.sets["open"].cases) == (30, 18)
    # The baseline is perfect on the table set by construction and not on the open set.
    assert results.sets["table"].baseline_coverage == 1
    assert results.sets["open"].baseline_coverage == pytest.approx(17 / 25)
    assert results.better_than_baseline_on_open is True
    assert results.cost_usd == pytest.approx(144 * 0.00015)


def test_a_dropped_output_and_a_wrong_type_show_in_the_numbers(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    recordings = tmp_path / "recordings"
    record_as_labelled(recordings, prompt, ALL)
    case = ALL[TABLE_CASE]
    wrong = case.label.wrong[0]
    put_call(
        run_folder(recordings, prompt.version, MODEL, 1),
        recorded_call(prompt, case.input, "not json"),
    )
    put_call(
        run_folder(recordings, prompt.version, MODEL, 2),
        recorded_call(prompt, case.input, output_text(*case.label.expected, wrong)),
    )

    runs, calls, drops = load_runs(ALL, prompt, MODEL, recordings)
    results = results_for(ALL, prompt, MODEL, runs, calls, load_bars(BARS))

    assert results.dropped == 1
    assert results.measures["harmful"].value == 1
    assert results.measures["harmful"].runs == [0, 1, 0]
    assert results.measures["stability"].value == pytest.approx(47 / 48)
    first_run = results.measures["coverage"].runs[0]
    assert first_run is not None
    assert first_run < 1
    assert results.all_bars_met is False
    assert list(drops) == [TABLE_CASE]
    report = table_report(ALL, runs, drops)
    line = next(line for line in report if line.startswith(TABLE_CASE))
    assert "run 1: invalid output dropped" in line
    assert f"run 2: wrong {wrong.value}" in line


def test_the_per_case_report_never_names_an_open_case(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(tmp_path / "recordings", prompt, ALL)
    runs, _, drops = load_runs(ALL, prompt, MODEL, tmp_path / "recordings")

    report = table_report(ALL, runs, drops)

    assert len(report) == 30
    assert not any("-open-" in line for line in report)


def test_the_printed_lines_say_each_measure_its_bar_and_met_or_missed(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(tmp_path / "recordings", prompt, ALL)
    runs, calls, _ = load_runs(ALL, prompt, MODEL, tmp_path / "recordings")

    out = lines(results_for(ALL, prompt, MODEL, runs, calls, load_bars(BARS)))

    assert out[0].startswith("risks-v1 (")
    assert "on gpt-6-luna, reasoning none, temperature 0: 3 runs of 48 cases" in out[0]
    assert [line.split()[0] for line in out[1:6]] == [
        "coverage",
        "precision",
        "harmful",
        "stability",
        "dropped",
    ]
    assert all(line.split("  each run")[0].rstrip().endswith("met") for line in out[1:5])
    assert "0 in 144 case-runs" in out[3]
    assert "(48 of 48 cases)" in out[4]
    assert out[5] == "dropped    0 of 144 outputs"
    assert out[6] == "no bar:"
    assert "table set (30 cases" in out[7]
    assert "rules-only baseline" in out[7]
    assert "open set (18 cases, 25 expected items)" in out[8]
    assert "coverage by risk type" in out[9]
    assert all(risk.value in out[9] for risk in RiskType)
    assert out[10].endswith("better than the rules-only baseline on the open set: yes")


def test_a_run_with_a_case_not_recorded_is_not_scored(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    recordings = tmp_path / "recordings"
    record_as_labelled(recordings, prompt, ALL)
    next(run_folder(recordings, prompt.version, MODEL, 3).glob("*.json")).unlink()

    with pytest.raises(NoRecordingsError, match="run 3"):
        load_runs(ALL, prompt, MODEL, recordings)


def test_recordings_made_with_another_text_of_the_prompt_do_not_count(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(tmp_path / "recordings", prompt, ALL)
    edited = write_prompt(tmp_path / "prompts", text="Rank the risks, but better.")

    with pytest.raises(NoRecordingsError):
        load_runs(ALL, edited, MODEL, tmp_path / "recordings")


def evals_folder(tmp_path: Path) -> Path:
    """A copy of the real cases and bars, with room for made-up recordings."""
    folder = tmp_path / "evals"
    (folder / "cases").mkdir(parents=True)
    for path in CASES.glob("*.json"):
        (folder / "cases" / path.name).write_text(path.read_text(encoding="utf-8"))
    (folder / "bars.toml").write_text((EVALS / "bars.toml").read_text(encoding="utf-8"))
    # Its own settings: these tests do not depend on which model the real results are for.
    (folder / "settings.toml").write_text(f'model = "{MODEL}"\ntemperature = 0\n')
    return folder


def test_make_eval_scores_the_recordings_and_writes_the_results_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evals = evals_folder(tmp_path)
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(evals / "recordings", prompt, ALL)
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]

    assert main(arguments) == 0
    assert main([*arguments, "--strict"]) == 0

    printed = capsys.readouterr().out
    assert "coverage" in printed
    assert "better than the rules-only baseline" in printed
    written = json.loads((evals / "results.json").read_text(encoding="utf-8"))
    assert written["prompt_version"] == "risks-v1"
    assert written["model"] == MODEL
    assert written["case_runs"] == 144
    assert sorted(written["measures"]) == ["coverage", "harmful", "precision", "stability"]
    # Totals only: no case is named in the results file.
    assert not any(name in json.dumps(written) for name in ALL)


def test_running_it_twice_writes_the_same_file(tmp_path: Path) -> None:
    evals = evals_folder(tmp_path)
    record_as_labelled(evals / "recordings", write_prompt(tmp_path / "prompts"), ALL)
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]

    main(arguments)
    first = (evals / "results.json").read_bytes()
    main(arguments)

    assert (evals / "results.json").read_bytes() == first


def test_strict_fails_on_a_missed_bar_and_plain_does_not(tmp_path: Path) -> None:
    evals = evals_folder(tmp_path)
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(evals / "recordings", prompt, ALL)
    case = ALL[TABLE_CASE]
    harmful = output_text(*case.label.expected, case.label.wrong[0])
    put_call(
        run_folder(evals / "recordings", prompt.version, MODEL, 1),
        recorded_call(prompt, case.input, harmful),
    )
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]

    assert main(arguments) == 0
    assert main([*arguments, "--strict"]) == 1
    assert json.loads((evals / "results.json").read_text())["all_bars_met"] is False


def test_a_prompt_with_no_recordings_is_a_failure_with_or_without_strict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evals = evals_folder(tmp_path)
    write_prompt(tmp_path / "prompts")
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]

    assert main(arguments) == 1
    assert main([*arguments, "--strict"]) == 1
    assert "was not scored" in capsys.readouterr().err
    assert not (evals / "results.json").exists()


def test_an_older_version_can_be_scored_without_touching_the_results_file(tmp_path: Path) -> None:
    evals = evals_folder(tmp_path)
    first = write_prompt(tmp_path / "prompts")
    second = write_prompt(tmp_path / "prompts", "risks-v2.md", "Second.")
    record_as_labelled(evals / "recordings", first, ALL)
    record_as_labelled(evals / "recordings", second, ALL)
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]

    assert main([*arguments, "--version", "risks-v1"]) == 0
    assert not (evals / "results.json").exists()
    assert main(arguments) == 0
    assert json.loads((evals / "results.json").read_text())["prompt_version"] == "risks-v2"


def test_the_real_settings_name_a_model_with_a_known_price() -> None:
    import tomllib

    from domain_health.risks.ledger import PRICES

    config = tomllib.loads((EVALS / "settings.toml").read_text(encoding="utf-8"))

    assert config["model"] in PRICES
    assert config.get("temperature", 0) == 0


def test_strict_fails_when_an_older_version_was_edited_after_it_was_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evals = evals_folder(tmp_path)
    first = write_prompt(tmp_path / "prompts")
    second = write_prompt(tmp_path / "prompts", "risks-v2.md", "Second.")
    record_as_labelled(evals / "recordings", first, ALL)
    record_as_labelled(evals / "recordings", second, ALL)
    arguments = ["--prompts", str(tmp_path / "prompts"), "--evals", str(evals)]
    assert main([*arguments, "--strict"]) == 0

    write_prompt(tmp_path / "prompts", text=first.text + " And one more line.")

    assert main(arguments) == 0
    assert main([*arguments, "--strict"]) == 1
    assert "no recordings match the prompt text of: risks-v1" in capsys.readouterr().err


def test_strict_accepts_an_older_version_recorded_on_another_model(tmp_path: Path) -> None:
    evals = evals_folder(tmp_path)
    first = write_prompt(tmp_path / "prompts")
    second = write_prompt(tmp_path / "prompts", "risks-v2.md", "Second.")
    record_as_labelled(evals / "recordings", first, ALL, model="gpt-6.1-terra")
    record_as_labelled(evals / "recordings", second, ALL)

    assert main(["--prompts", str(tmp_path / "prompts"), "--evals", str(evals), "--strict"]) == 0
