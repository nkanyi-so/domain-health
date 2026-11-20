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
from domain_health.seeded.recording_report import (
    LINES,
    false_wording,
    lines,
    off_the_line,
    report,
)
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


def state_off_the_line(kind: RiskType) -> State:
    """A seeded state on the side of this type's line where the rubric does not list it."""
    for state in STATES:
        if off_the_line(kind, state.snapshot) is not None:
            return state
    raise AssertionError(f"no seeded state is off the line of {kind.value}")


def one_risk(kind: RiskType, why: str) -> str:
    return json.dumps(
        {"risks": [{"type": kind.value, "title": "A title", "why": why, "evidence": ["fixes"]}]}
    )


@pytest.mark.parametrize(
    ("kind", "why", "flagged"),
    [
        (RiskType.COMPLAINT_RATE_ELEVATED, "The rate is above the recommended level.", True),
        (RiskType.COMPLAINT_RATE_ELEVATED, "Complaints are elevated.", True),
        (RiskType.COMPLAINT_RATE_ELEVATED, "Too many recipients object.", True),
        (RiskType.COMPLAINT_RATE_ELEVATED, "Worth watching while the list is new.", False),
        (RiskType.BOUNCE_RATE_ELEVATED, "The rate exceeds what receivers accept.", True),
        (RiskType.BOUNCE_RATE_ELEVATED, "Bounces are high.", True),
        (RiskType.BOUNCE_RATE_ELEVATED, "Worth a look at list hygiene.", False),
        (RiskType.VOLUME_SPIKE, "Volume has spiked this week.", True),
        (RiskType.VOLUME_SPIKE, "A sharp rise in sending.", True),
        (RiskType.VOLUME_SPIKE, "Sending is steady week on week.", False),
        (RiskType.ENGAGEMENT_DECLINING, "The open rate is sharply down.", True),
        (RiskType.ENGAGEMENT_DECLINING, "Opens have fallen.", True),
        (RiskType.ENGAGEMENT_DECLINING, "Opens are about where they were.", False),
        (RiskType.SPF_NEAR_LOOKUP_LIMIT, "The record is near the lookup limit.", True),
        (RiskType.SPF_NEAR_LOOKUP_LIMIT, "The record is approaching ten lookups.", True),
        (RiskType.SPF_NEAR_LOOKUP_LIMIT, "The record has room to grow.", False),
        (RiskType.NEW_DOMAIN_VOLUME, "A new domain sending in bulk.", True),
        (RiskType.NEW_DOMAIN_VOLUME, "The domain was registered recently.", True),
        (RiskType.NEW_DOMAIN_VOLUME, "Sending is in bulk.", False),
    ],
)
def test_text_that_says_a_value_is_over_a_rubric_line_it_is_not_over_is_flagged(
    prompt: Prompt, kind: RiskType, why: str, flagged: bool
) -> None:
    state = state_off_the_line(kind)
    text = one_risk(kind, why)
    risks = risks_from(state.snapshot, recorded_call(prompt, state.snapshot, text))

    assert bool(false_wording(state.snapshot, risks)) is flagged
    found = report([state], calls(prompt, state.snapshot, text, text, text))[0]
    assert bool(found.false_wording) is flagged


SAID = {
    RiskType.COMPLAINT_RATE_ELEVATED: "The rate is elevated.",
    RiskType.BOUNCE_RATE_ELEVATED: "The rate is elevated.",
    RiskType.VOLUME_SPIKE: "Volume has spiked.",
    RiskType.ENGAGEMENT_DECLINING: "Opens have fallen.",
    RiskType.SPF_NEAR_LOOKUP_LIMIT: "Near the limit.",
    RiskType.NEW_DOMAIN_VOLUME: "A new domain.",
}


def test_the_same_words_on_the_listed_side_of_the_line_are_not_flagged(prompt: Prompt) -> None:
    assert set(SAID) == set(LINES)
    for kind, why in SAID.items():
        listed = [
            s
            for s in STATES
            if off_the_line(kind, s.snapshot) is None
            and kind in table_label(s.snapshot).expected + table_label(s.snapshot).acceptable
        ]
        assert listed, kind
        text = one_risk(kind, why)
        risks = risks_from(listed[0].snapshot, recorded_call(prompt, listed[0].snapshot, text))
        assert false_wording(listed[0].snapshot, risks) == []


def test_each_line_is_where_the_rubrics_bands_start_to_list_the_type() -> None:
    """The lines are written in the report and not read from the rubric's table, so this ties
    them to it: among the seeded states, an input off the line is never expected or acceptable
    for that type, and every type has a seeded state on each side."""
    for kind in LINES:
        off = [s for s in STATES if off_the_line(kind, s.snapshot) is not None]
        assert off, kind
        for state in off:
            label = table_label(state.snapshot)
            assert kind not in label.expected + label.acceptable, (kind, state.client_id)


def test_every_risk_type_whose_bands_turn_on_a_number_has_a_line() -> None:
    assert set(LINES) == {
        RiskType.COMPLAINT_RATE_ELEVATED,
        RiskType.BOUNCE_RATE_ELEVATED,
        RiskType.VOLUME_SPIKE,
        RiskType.ENGAGEMENT_DECLINING,
        RiskType.SPF_NEAR_LOOKUP_LIMIT,
        RiskType.NEW_DOMAIN_VOLUME,
    }


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
