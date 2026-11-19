"""The recorded and the fixture model: both give validated risks or say they have none."""

from pathlib import Path

import pytest

from domain_health.evals.cases import load_cases
from domain_health.risks.model import (
    FixtureRiskModel,
    RecordedRiskModel,
    RisksUnavailableError,
    call_key,
    input_hash,
    load_calls,
    save_call,
    user_message,
)
from domain_health.types import RiskType
from tests.dns_fixtures import run
from tests.eval_fixtures import MODEL, output_text, recorded_call, write_prompt
from tests.paths import CASES

TABLE = {name: case for name, case in load_cases(CASES).items() if case.set == "table"}
ONE = TABLE["06-dmarc-none-established"].input
OTHER = TABLE["01-healthy-baseline"].input


def test_a_recording_is_replayed_and_validated(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    call = recorded_call(prompt, ONE, output_text(RiskType.DMARC_POLICY_NONE))

    risks = run(RecordedRiskModel(prompt, MODEL, [call]).rank(ONE))

    assert [risk.id for risk in risks] == [f"dmarc_policy_none:{ONE.domain}"]


def test_an_input_with_no_recording_has_no_risks(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    call = recorded_call(prompt, ONE, output_text())

    with pytest.raises(RisksUnavailableError, match="no recording"):
        run(RecordedRiskModel(prompt, MODEL, [call]).rank(OTHER))


def test_a_recording_is_found_by_prompt_version_model_and_input(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    call = recorded_call(prompt, ONE, output_text())

    assert RecordedRiskModel(prompt, MODEL, [call]).recorded(ONE) == call
    # Another model's recording, another version's, and one made with an edited prompt text.
    assert RecordedRiskModel(prompt, "gpt-6.1-terra", [call]).recorded(ONE) is None
    second = write_prompt(tmp_path, "risks-v2.md")
    assert RecordedRiskModel(second, MODEL, [call]).recorded(ONE) is None
    edited = write_prompt(tmp_path, text="Rank the risks, differently.")
    assert RecordedRiskModel(edited, MODEL, [call]).recorded(ONE) is None
    assert call_key("risks-v1", MODEL, "a") != call_key("risks-v1", MODEL, "b")


def test_recorded_output_that_breaks_a_rule_is_dropped_at_replay(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path)
    twice = output_text(RiskType.VOLUME_SPIKE, RiskType.VOLUME_SPIKE)
    model = RecordedRiskModel(prompt, MODEL, [recorded_call(prompt, ONE, twice)])

    with pytest.raises(RisksUnavailableError, match="invalid output dropped"):
        run(model.rank(ONE))


@pytest.mark.parametrize("status", ["refused", "incomplete", "error"])
def test_a_call_that_did_not_complete_has_no_risks(tmp_path: Path, status: str) -> None:
    prompt = write_prompt(tmp_path)
    call = recorded_call(prompt, ONE, None, status=status)

    with pytest.raises(RisksUnavailableError, match=status):
        run(RecordedRiskModel(prompt, MODEL, [call]).rank(ONE))


def test_recordings_are_saved_one_file_an_input_and_loaded_back(tmp_path: Path) -> None:
    prompt = write_prompt(tmp_path / "prompts")
    calls = [recorded_call(prompt, snapshot, output_text()) for snapshot in (ONE, OTHER)]

    paths = [save_call(tmp_path / "run-1", call) for call in calls]

    assert sorted(path.name for path in paths) == sorted(
        f"{input_hash(snapshot)[:16]}.json" for snapshot in (ONE, OTHER)
    )
    assert sorted(load_calls(tmp_path / "run-1"), key=lambda c: c.input_hash) == sorted(
        calls, key=lambda c: c.input_hash
    )


def test_the_fixture_model_answers_from_its_script_and_validates_it() -> None:
    model = FixtureRiskModel(
        {ONE.domain: output_text(RiskType.DKIM_KEY_1024), OTHER.domain: "not json"}
    )

    assert [risk.type for risk in run(model.rank(ONE))] == [RiskType.DKIM_KEY_1024]
    with pytest.raises(RisksUnavailableError, match="invalid output dropped"):
        run(model.rank(OTHER))
    with pytest.raises(RisksUnavailableError, match="no scripted output"):
        run(model.rank(TABLE["03-healthy-seasonal-spike"].input))
    assert model.seen[0] == ONE


def test_the_message_sent_for_an_input_is_the_input_and_nothing_else() -> None:
    assert ONE.model_validate_json(user_message(ONE)) == ONE
