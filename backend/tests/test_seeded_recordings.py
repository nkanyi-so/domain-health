"""The seeded clients' recordings: which answers are kept, and what the report says of them.

The tests at the end read the committed recordings: every seeded state has its three answers,
no kept answer names a type the rubric's bands call wrong, and none says a rate is elevated
when it is under the rubric's line.
"""

import json
from pathlib import Path

import pytest

from domain_health.evals.table import table_label
from domain_health.models import SnapshotInput
from domain_health.risks.model import ModelCall, RisksUnavailableError, input_hash, risks_from
from domain_health.risks.prompt import Prompt
from domain_health.seeded.record import still_to_record
from domain_health.seeded.recording_report import RATE_LINES, false_wording, lines, report
from domain_health.seeded.recordings import (
    RUNS,
    State,
    agreement,
    kept_calls,
    recorded_model,
    recorded_runs,
    run_folder,
    settings,
    states,
)
from domain_health.types import RiskType
from tests.dns_fixtures import run
from tests.eval_fixtures import MODEL, output_text, put_call, recorded_call, write_prompt

STATES = run(states())


def a_state_with(band: str, count: int = 1) -> tuple[State, list[RiskType]]:
    """A seeded state whose rubric label has at least `count` types in this band."""
    for state in STATES:
        kinds = list(getattr(table_label(state.snapshot), band))
        if len(kinds) >= count:
            return state, kinds
    raise AssertionError(f"no seeded state has {count} {band} type(s)")


def calls(prompt: Prompt, snapshot: SnapshotInput, *texts: str | None) -> list[list[ModelCall]]:
    return [[recorded_call(prompt, snapshot, text)] for text in texts]


@pytest.fixture
def prompt(tmp_path: Path) -> Prompt:
    return write_prompt(tmp_path / "prompts")


def test_there_are_twenty_six_states_and_each_is_a_different_input() -> None:
    assert len(STATES) == 26
    assert len({input_hash(state.snapshot) for state in STATES}) == 26
    assert len({state.client_id for state in STATES}) == 12


def test_three_answers_with_the_same_first_five_agree(prompt: Prompt) -> None:
    state = STATES[0]
    kinds = list(RiskType)[:7]
    same_five = [output_text(*kinds[:5], *tail) for tail in ([], kinds[5:6], kinds[5:7])]

    assert agreement(state.snapshot, calls(prompt, state.snapshot, *same_five)) == "agreed"


@pytest.mark.parametrize(
    ("texts", "verdict"),
    [
        (("a", "a", "b"), "disagreed"),
        (("a", "a", "reordered"), "disagreed"),
        (("a", "a", "not json"), "invalid"),
        (("a", "a", None), "invalid"),
    ],
)
def test_answers_that_differ_or_are_not_valid_are_not_kept(
    prompt: Prompt, texts: tuple[str | None, ...], verdict: str
) -> None:
    state = STATES[0]
    kinds = list(RiskType)
    named = {
        "a": output_text(*kinds[:3]),
        "b": output_text(*kinds[:2]),
        "reordered": output_text(kinds[1], kinds[0], kinds[2]),
    }
    runs = calls(prompt, state.snapshot, *(named.get(t, t) if t else None for t in texts))

    assert agreement(state.snapshot, runs) == verdict
    assert kept_calls([state], runs) == []


def test_a_state_with_fewer_than_three_answers_is_missing(prompt: Prompt) -> None:
    state = STATES[0]
    two = [*calls(prompt, state.snapshot, output_text(), output_text()), []]

    assert agreement(state.snapshot, two) == "missing"


def test_the_kept_answer_is_the_first_runs_and_only_for_states_that_agree(prompt: Prompt) -> None:
    first, second = STATES[0], STATES[1]
    kinds = list(RiskType)
    runs = [
        [
            recorded_call(prompt, first.snapshot, output_text(kinds[0])),
            recorded_call(prompt, second.snapshot, output_text(kinds[0])),
        ],
        [
            recorded_call(prompt, first.snapshot, output_text(kinds[0])),
            recorded_call(prompt, second.snapshot, output_text(kinds[1])),
        ],
        [
            recorded_call(prompt, first.snapshot, output_text(kinds[0])),
            recorded_call(prompt, second.snapshot, output_text(kinds[0])),
        ],
    ]

    assert kept_calls([first, second], runs) == [runs[0][0]]


def test_the_report_counts_what_the_bands_call_acceptable_and_wrong(prompt: Prompt) -> None:
    state, acceptable = a_state_with("acceptable")
    wrong = table_label(state.snapshot).wrong
    text = output_text(acceptable[0], wrong[0])

    found = report([state], calls(prompt, state.snapshot, text, text, text))[0]

    assert found.agreement == "agreed"
    assert found.merely_acceptable == [acceptable[0]]
    assert found.wrong == [wrong[0]]
    printed = "\n".join(lines([found], prompt, MODEL))
    assert f"merely acceptable: {acceptable[0].value}" in printed
    assert f"WRONG by the bands: {wrong[0].value}" in printed
    assert "1 of a type the bands call merely acceptable, 1 wrong" in printed


def low_rate_state(kind: RiskType) -> State:
    field, line = RATE_LINES[kind]
    for state in STATES:
        if float(getattr(state.snapshot.sources, field)) < line:
            return state
    raise AssertionError("no seeded state is under the line")


@pytest.mark.parametrize("kind", list(RATE_LINES))
@pytest.mark.parametrize(
    ("why", "flagged"),
    [
        ("The rate is above the level mailbox providers recommend.", True),
        ("Complaints are elevated.", True),
        ("The rate exceeds what receivers accept.", True),
        ("Too many recipients object.", True),
        ("Worth watching while the list is new.", False),
    ],
)
def test_text_that_says_a_rate_is_elevated_under_the_rubrics_line_is_flagged(
    prompt: Prompt, kind: RiskType, why: str, flagged: bool
) -> None:
    state = low_rate_state(kind)
    text = json.dumps(
        {"risks": [{"type": kind.value, "title": "A title", "why": why, "evidence": ["fixes"]}]}
    )
    risks = risks_from(state.snapshot, recorded_call(prompt, state.snapshot, text))

    assert bool(false_wording(state.snapshot, risks)) is flagged
    found = report([state], calls(prompt, state.snapshot, text, text, text))[0]
    assert bool(found.false_wording) is flagged


def test_the_same_words_at_a_rate_over_the_line_are_not_flagged(prompt: Prompt) -> None:
    for kind, (field, line) in RATE_LINES.items():
        over = [s for s in STATES if float(getattr(s.snapshot.sources, field)) >= line]
        assert over, kind
        text = json.dumps(
            {
                "risks": [
                    {
                        "type": kind.value,
                        "title": "A title",
                        "why": "The rate is elevated.",
                        "evidence": ["fixes"],
                    }
                ]
            }
        )
        risks = risks_from(over[0].snapshot, recorded_call(prompt, over[0].snapshot, text))
        assert false_wording(over[0].snapshot, risks) == []


def test_each_rate_line_is_where_the_rubrics_bands_start_to_list_the_type() -> None:
    """The lines are written here and not read from the rubric's table, so this ties them to
    it: among the seeded states, a rate under the line is never expected or acceptable."""
    for kind, (field, line) in RATE_LINES.items():
        for state in STATES:
            label = table_label(state.snapshot)
            if float(getattr(state.snapshot.sources, field)) < line:
                assert kind not in label.expected + label.acceptable, state.client_id


def test_only_what_the_model_has_not_answered_is_still_to_record(
    tmp_path: Path, prompt: Prompt
) -> None:
    first, second = STATES[0].snapshot, STATES[1].snapshot
    recordings = tmp_path / "recordings"
    put_call(run_folder(recordings, prompt.version, MODEL, 1), recorded_call(prompt, first, "{}"))
    failed = recorded_call(prompt, second, None).model_copy(update={"status": "error"})
    put_call(run_folder(recordings, prompt.version, MODEL, 1), failed)

    todo = still_to_record([first, second], prompt, MODEL, recordings)

    # An answer, valid or not, is never asked for again; a call that failed is.
    assert todo == {1: [second], 2: [first, second], 3: [first, second]}


def test_recordings_made_with_another_text_of_the_prompt_do_not_count(
    tmp_path: Path, prompt: Prompt
) -> None:
    snapshot = STATES[0].snapshot
    recordings = tmp_path / "recordings"
    for number in range(1, RUNS + 1):
        put_call(
            run_folder(recordings, prompt.version, MODEL, number),
            recorded_call(prompt, snapshot, output_text()),
        )
    edited = write_prompt(tmp_path / "prompts", text="Rank the risks, differently.")

    assert all(len(calls_) == 1 for calls_ in recorded_runs(prompt, MODEL, recordings))
    assert recorded_runs(edited, MODEL, recordings) == [[], [], []]


# --- The committed recordings ---


def committed() -> tuple[Prompt, str, list[list[ModelCall]]]:
    prompt, model = settings()
    return prompt, model, recorded_runs(prompt, model)


def test_the_prompt_in_use_is_the_one_the_settings_name() -> None:
    prompt, model, _ = committed()

    assert (prompt.version, model) == ("risks-v3", "gpt-6.1-terra")


def test_every_seeded_state_has_its_three_recorded_answers() -> None:
    _, _, runs = committed()

    missing = [
        f"{state.client_id} day {state.day_index}"
        for state in STATES
        if agreement(state.snapshot, runs) == "missing"
    ]

    assert missing == []


def test_no_kept_recording_names_a_type_the_rubrics_bands_call_wrong() -> None:
    _, _, runs = committed()

    wrong = {
        f"{found.client_id} day {found.day_index}": [kind.value for kind in found.wrong]
        for found in report(STATES, runs)
        if found.agreement == "agreed" and found.wrong
    }

    assert wrong == {}


def test_no_kept_recording_says_a_rate_is_elevated_under_the_rubrics_line() -> None:
    _, _, runs = committed()

    flagged = {
        f"{found.client_id} day {found.day_index}": found.false_wording
        for found in report(STATES, runs)
        if found.agreement == "agreed" and found.false_wording
    }

    assert flagged == {}


def test_the_deployed_model_replays_exactly_the_kept_answers() -> None:
    model, prompt, _ = recorded_model()
    _, _, runs = committed()

    for state in STATES:
        if agreement(state.snapshot, runs) == "agreed":
            first = next(c for c in runs[0] if c.input_hash == input_hash(state.snapshot))
            assert run(model.rank(state.snapshot)) == risks_from(state.snapshot, first)
        else:
            with pytest.raises(RisksUnavailableError):
                run(model.rank(state.snapshot))
    assert prompt.version == "risks-v3"
