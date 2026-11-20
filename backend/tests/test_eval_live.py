"""The paid command's own logic, with a scripted model in place of the live one."""

import asyncio
from pathlib import Path

import pytest

from domain_health.evals import live
from domain_health.evals.cases import load_cases
from domain_health.evals.live import (
    LOCK_FILE,
    AnotherRunError,
    PromptChangedError,
    _OnlyOneRun,
    record_runs,
    refuse_a_prompt_already_run,
    refuse_an_edited_prompt,
    still_to_record,
)
from domain_health.evals.report import load_runs, run_folder
from domain_health.models import SnapshotInput
from domain_health.risks.model import ModelCall, input_hash, load_calls
from tests.dns_fixtures import run
from tests.eval_fixtures import (
    MODEL,
    output_text,
    put_call,
    record_as_labelled,
    recorded_call,
    write_prompt,
)
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
    put_call(folder, recorded_call(prompt, invalid, "not json"))
    put_call(folder, recorded_call(prompt, failed, None, status="error"))

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


def test_a_prompt_that_breaks_a_rule_is_refused_before_any_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    called: list[object] = []
    monkeypatch.setattr(live, "record_runs", lambda *args: called.append(args))
    domain = next(iter(ALL.values())).input.domain
    write_prompt(tmp_path / "prompts", text=f"Rank the risks, as for {domain}.")

    assert live.main(arguments(tmp_path)) == 1
    assert "breaks a rule for prompts, so it was not run" in capsys.readouterr().err
    assert called == []


def test_a_prompt_edited_after_it_was_run_is_refused_and_nothing_is_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recordings = tmp_path / "evals" / "recordings"
    prompt = write_prompt(tmp_path / "prompts")
    record_as_labelled(recordings, prompt, ALL)
    before = sorted(path.read_bytes() for path in recordings.rglob("*.json"))
    refuse_an_edited_prompt(prompt, MODEL, recordings)  # unchanged: nothing to refuse

    edited = write_prompt(tmp_path / "prompts", text=prompt.text + "\n")

    with pytest.raises(PromptChangedError, match="new version file"):
        refuse_an_edited_prompt(edited, MODEL, recordings)
    # A model with nothing recorded under this name is not affected.
    refuse_an_edited_prompt(edited, "gpt-6.1-terra", recordings)

    # Through the command: it stops before any call, and the recordings are as they were.
    evals = tmp_path / "evals"
    (evals / "cases").mkdir()
    for path in CASES.glob("*.json"):
        (evals / "cases" / path.name).write_text(path.read_text(encoding="utf-8"))
    for name in ("RUBRIC.md", "bars.toml"):
        (evals / name).write_text((EVALS / name).read_text(encoding="utf-8"))
    (evals / "settings.toml").write_text(f'model = "{MODEL}"\ntemperature = 0\n')
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    called: list[object] = []
    monkeypatch.setattr(live, "record_runs", lambda *args: called.append(args))
    command = [
        "--prompts", str(tmp_path / "prompts"),
        "--evals", str(evals),
        "--standing", str(REPO / "docs" / "STANDING.md"),
    ]  # fmt: skip

    assert live.main(command) == 1
    assert "A changed prompt is a new version file" in capsys.readouterr().err
    assert called == []
    assert sorted(path.read_bytes() for path in recordings.rglob("*.json")) == before


def test_the_same_text_under_a_new_version_name_is_not_run_again(tmp_path: Path) -> None:
    recordings = tmp_path / "recordings"
    third = write_prompt(tmp_path / "prompts", "risks-v3.md", "The third version.")
    record_as_labelled(recordings, third, ALL)

    copy = write_prompt(tmp_path / "prompts", "risks-v4.md", third.text)
    with pytest.raises(PromptChangedError, match="already recorded on gpt-6-luna as risks-v3"):
        refuse_a_prompt_already_run(copy, MODEL, recordings)

    # A real change is a new prompt, and the same text on another model is another attempt.
    changed = write_prompt(tmp_path / "prompts", "risks-v4.md", third.text + " Changed.")
    refuse_a_prompt_already_run(changed, MODEL, recordings)
    refuse_a_prompt_already_run(copy, "gpt-6.1-terra", recordings)
    refuse_a_prompt_already_run(third, MODEL, recordings)


def test_when_one_call_fails_the_others_of_the_run_still_finish_and_are_saved(
    tmp_path: Path,
) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    recordings = tmp_path / "recordings"
    inputs = [case.input for case in list(ALL.values())[:12]]
    finished: list[str] = []

    async def scripted(snapshot: SnapshotInput) -> ModelCall:
        if snapshot == inputs[3]:
            raise RuntimeError("this request was refused")
        await asyncio.sleep(0.01)
        finished.append(snapshot.domain)
        return recorded_call(prompt, snapshot, output_text())

    said: list[str] = []
    with pytest.raises(RuntimeError, match="refused"):
        run(
            record_runs(
                scripted,
                {1: inputs, 2: inputs},
                lambda number: run_folder(recordings, prompt.version, MODEL, number),
                said.append,
            )
        )

    # Eleven of the first run's twelve were let finish and are on disk; the second run, which
    # had not started, was not begun.
    assert len(finished) == 11
    assert len(load_calls(run_folder(recordings, prompt.version, MODEL, 1))) == 11
    assert said == ["run 1: 11 call(s) recorded"]
    assert not run_folder(recordings, prompt.version, MODEL, 2).exists()


def test_only_one_paid_run_at_a_time(tmp_path: Path) -> None:
    lock = tmp_path / LOCK_FILE

    with _OnlyOneRun(lock):
        assert lock.exists()
        with pytest.raises(AnotherRunError, match="another paid run"), _OnlyOneRun(lock):
            pass
        assert lock.exists()
    assert not lock.exists()

    # Released on the way out even when the run fails.
    with pytest.raises(RuntimeError), _OnlyOneRun(lock):
        raise RuntimeError("the run failed")
    assert not lock.exists()


def test_the_command_takes_the_lock_before_anything_that_can_spend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "settings.toml").write_text(f'model = "{MODEL}"\ntemperature = 0\n')
    (evals / LOCK_FILE).write_text("")
    reached: list[object] = []
    monkeypatch.setattr(live, "_paid", lambda *args: reached.append(args))
    command = [
        "--prompts", str(tmp_path / "prompts"),
        "--evals", str(evals),
        "--standing", str(REPO / "docs" / "STANDING.md"),
    ]  # fmt: skip

    assert live.main(command) == 1
    assert reached == []
    assert "another paid run is in progress" in capsys.readouterr().err
    assert (evals / LOCK_FILE).exists()


def test_the_command_refuses_a_copied_prompt_before_any_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    evals = tmp_path / "evals"
    (evals / "cases").mkdir(parents=True)
    for path in CASES.glob("*.json"):
        (evals / "cases" / path.name).write_text(path.read_text(encoding="utf-8"))
    for name in ("RUBRIC.md", "bars.toml"):
        (evals / name).write_text((EVALS / name).read_text(encoding="utf-8"))
    (evals / "settings.toml").write_text(f'model = "{MODEL}"\ntemperature = 0\n')
    third = write_prompt(tmp_path / "prompts", "risks-v3.md", "The third version.")
    record_as_labelled(evals / "recordings", third, ALL)
    before = sorted(path.read_bytes() for path in (evals / "recordings").rglob("*.json"))
    write_prompt(tmp_path / "prompts", "risks-v4.md", third.text)
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    called: list[object] = []
    monkeypatch.setattr(live, "record_runs", lambda *args: called.append(args))
    command = [
        "--prompts", str(tmp_path / "prompts"),
        "--evals", str(evals),
        "--standing", str(REPO / "docs" / "STANDING.md"),
    ]  # fmt: skip

    assert live.main(command) == 1
    assert "An unchanged prompt is never run again" in capsys.readouterr().err
    assert called == []
    assert sorted(path.read_bytes() for path in (evals / "recordings").rglob("*.json")) == before
    assert not (evals / LOCK_FILE).exists()


def test_a_version_run_while_another_is_in_use_is_scored_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scoring by name leaves the results file alone: it stays the version in use's."""
    (tmp_path / "settings.toml").write_text(f'model = "{MODEL}"\nprompt = "risks-v1"\n')
    prompts = tmp_path / "prompts"
    base = ["--prompts", str(prompts), "--evals", str(tmp_path), "--table-report"]

    assert live.scoring_arguments(prompts, tmp_path, "risks-v2", None) == [
        *base,
        "--version",
        "risks-v2",
    ]
    assert "the prompt in use is risks-v1" in capsys.readouterr().out
    assert live.scoring_arguments(prompts, tmp_path, "risks-v1", "other") == [
        *base,
        "--model",
        "other",
    ]
    (tmp_path / "settings.toml").write_text(f'model = "{MODEL}"\n')
    assert live.scoring_arguments(prompts, tmp_path, "risks-v2", None) == base
