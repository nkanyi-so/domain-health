"""The paid command's own logic, with a scripted model in place of the live one."""

from pathlib import Path

import pytest

from domain_health.evals import live
from domain_health.evals.cases import load_cases
from domain_health.evals.live import record_runs, still_to_record
from domain_health.evals.report import load_runs, run_folder
from domain_health.models import SnapshotInput
from domain_health.risks.model import ModelCall, input_hash, load_calls, save_call
from tests.dns_fixtures import run
from tests.eval_fixtures import MODEL, output_text, record_as_labelled, recorded_call, write_prompt
from tests.paths import CASES, EVALS, REPO

ALL = load_cases(CASES)


def test_before_any_run_every_case_is_to_record_in_each_of_three_runs(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")

    todo = still_to_record(ALL, prompt, MODEL, tmp_path / "recordings")

    assert sorted(todo) == [1, 2, 3]
    assert all(len(inputs) == 48 for inputs in todo.values())


def test_a_prompt_version_with_its_three_runs_recorded_has_nothing_left_to_run(
    tmp_path: Path,
) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(tmp_path / "recordings", prompt, ALL)

    assert still_to_record(ALL, prompt, MODEL, tmp_path / "recordings") == {}
    # Another model, or a changed prompt text, has not been run.
    assert len(still_to_record(ALL, prompt, "gpt-6.1-terra", tmp_path / "recordings")) == 3
    edited = write_prompt(tmp_path / "prompts", text="Changed.")
    assert len(still_to_record(ALL, edited, MODEL, tmp_path / "recordings")) == 3


def test_an_answer_is_never_asked_for_again_but_a_failed_call_is(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    recordings = tmp_path / "recordings"
    record_as_labelled(recordings, prompt, ALL)
    invalid, failed = (ALL[name].input for name in list(ALL)[:2])
    folder = run_folder(recordings, prompt.version, MODEL, 2)
    # Output that fails validation is still the model's answer. A call that never got one is not.
    save_call(folder, recorded_call(prompt, invalid, "not json"))
    save_call(folder, recorded_call(prompt, failed, None, status="error"))

    todo = still_to_record(ALL, prompt, MODEL, recordings)

    assert list(todo) == [2]
    assert todo[2] == [failed]


def test_every_call_is_saved_under_its_run_and_only_inputs_are_passed(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    recordings = tmp_path / "recordings"
    seen: list[object] = []

    async def scripted(snapshot: SnapshotInput) -> ModelCall:
        seen.append(snapshot)
        return recorded_call(prompt, snapshot, output_text())

    todo = still_to_record(ALL, prompt, MODEL, recordings)
    said: list[str] = []
    made = run(
        record_runs(
            scripted,
            todo,
            lambda number: run_folder(recordings, prompt.version, MODEL, number),
            said.append,
        )
    )

    assert made == 144
    assert all(isinstance(item, SnapshotInput) for item in seen)
    assert said == [f"run {n}: 48 call(s) recorded" for n in (1, 2, 3)]
    for number in (1, 2, 3):
        folder = run_folder(recordings, prompt.version, MODEL, number)
        assert {call.input_hash for call in load_calls(folder)} == {
            input_hash(case.input) for case in ALL.values()
        }
    runs, _, _ = load_runs(ALL, prompt, MODEL, recordings)
    assert len(runs) == 3


def arguments(tmp_path: Path) -> list[str]:
    return [
        "--prompts", str(tmp_path / "prompts"),
        "--evals", str(EVALS),
        "--standing", str(REPO / "docs" / "STANDING.md"),
    ]  # fmt: skip


def test_without_a_key_nothing_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    write_prompt(tmp_path / "prompts")

    assert live.main(arguments(tmp_path)) == 1
    assert "OPENAI_API_KEY is not set" in capsys.readouterr().err


def test_a_recorded_prompt_version_is_refused_before_any_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Never a real key: the client is built but the run stops before any request.
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    monkeypatch.setattr(live, "still_to_record", lambda *args: {})
    write_prompt(tmp_path / "prompts")

    assert live.main(arguments(tmp_path)) == 1
    assert "An unchanged prompt is never run again" in capsys.readouterr().err
