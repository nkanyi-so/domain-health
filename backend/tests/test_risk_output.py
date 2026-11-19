"""The model's output is untrusted: what is accepted, what is dropped, and who builds the ID."""

import json
from decimal import Decimal

import pytest
from pydantic import BaseModel

from domain_health.evals.cases import load_cases
from domain_health.models import SnapshotInput
from domain_health.risks import (
    EVIDENCE_FIELDS,
    MAX_RISKS,
    InvalidOutputError,
    ModelOutput,
    numbers_in,
    risk_id,
    validate,
)
from domain_health.types import RiskType
from tests.paths import CASES

# A table case: complaints 0.12 on 18,400 messages, a 1,024-bit key, DMARC at p=none.
SNAPSHOT = load_cases(CASES)["06-dmarc-none-established"].input


def risk(risk_type: str, title: str = "A title", why: str = "A reason.") -> dict[str, object]:
    return {"type": risk_type, "title": title, "why": why, "evidence": ["checks.dmarc.policy"]}


def output(*risks: dict[str, object]) -> str:
    return json.dumps({"risks": list(risks)})


def test_a_valid_output_keeps_the_models_order_and_wording() -> None:
    text = output(
        risk("dmarc_policy_none", "DMARC only monitors", "  Nothing is refused. "),
        risk("reputation_poor"),
    )

    risks = validate(SNAPSHOT, text)

    assert [r.type for r in risks] == [RiskType.DMARC_POLICY_NONE, RiskType.REPUTATION_POOR]
    assert risks[0].title == "DMARC only monitors"
    assert risks[0].why == "Nothing is refused."
    assert risks[0].evidence == ["checks.dmarc.policy"]


def test_the_id_is_built_in_code_from_the_type_and_the_domain() -> None:
    risks = validate(SNAPSHOT, output(risk("dmarc_policy_none", title="id: something-else")))

    assert risks[0].id == f"dmarc_policy_none:{SNAPSHOT.domain}"
    assert risk_id(RiskType.VOLUME_SPIKE, "a.example") == "volume_spike:a.example"
    # The same input gives the same IDs, whatever the model wrote around them.
    again = validate(SNAPSHOT, output(risk("dmarc_policy_none", title="Other words")))
    assert [r.id for r in again] == [r.id for r in risks]


def test_the_model_has_no_field_to_put_an_id_in() -> None:
    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, output(risk("dmarc_policy_none") | {"id": "mine"}))


def test_no_risks_is_a_valid_answer() -> None:
    assert validate(SNAPSHOT, output()) == []


def test_an_unknown_type_is_rejected() -> None:
    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, output(risk("spf_missing")))
    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, output(risk("made_up_risk")))


def test_a_duplicate_is_rejected() -> None:
    with pytest.raises(InvalidOutputError, match="twice"):
        validate(SNAPSHOT, output(risk("dmarc_policy_none"), risk("dmarc_policy_none")))


def test_eight_are_accepted_and_a_ninth_is_rejected() -> None:
    types = [t.value for t in RiskType]

    assert len(validate(SNAPSHOT, output(*(risk(t) for t in types[:MAX_RISKS])))) == 8
    with pytest.raises(InvalidOutputError, match="more than 8"):
        validate(SNAPSHOT, output(*(risk(t) for t in types[:9])))


@pytest.mark.parametrize(
    "why",
    [
        "Complaints are at 0.5%.",
        "Complaints are near the 0.3% limit.",
        "Volume grew 2x in a week.",
        "About 18k messages went out.",
        "The domain is 3 years old.",
        "Rotate within 30 days.",
        "Version 1.2.3 of the record.",
        "Since 2026-11-19 it has been falling.",
    ],
)
def test_a_number_that_is_not_in_the_input_is_rejected(why: str) -> None:
    with pytest.raises(InvalidOutputError, match="not in the input"):
        validate(SNAPSHOT, output(risk("complaint_rate_elevated", why=why)))


def test_an_invented_number_in_the_title_is_rejected_too() -> None:
    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, output(risk("complaint_rate_elevated", title="Complaints at 9%")))


def test_numbers_from_the_input_may_be_cited_however_they_are_written() -> None:
    sources = SNAPSHOT.sources
    key = SNAPSHOT.checks.dkim.keys[0]
    why = (
        f"Complaints are {sources.complaint_rate_pct}% on {sources.volume_7d:,} messages, "
        f"up from {sources.volume_prev_7d}; the {key.key_bits}-bit key at {key.selector} and "
        f"spf1 are fine; the domain is {sources.domain_age_days} days old."
    )

    assert len(validate(SNAPSHOT, output(risk("complaint_rate_elevated", why=why)))) == 1


def test_words_that_only_hold_a_digit_are_not_numbers() -> None:
    assert numbers_in("spf1, s1, DKIM1, sha256 and p=none v2") == set()
    assert numbers_in("0.120 and 18,400 and 1,024-bit.") == {
        Decimal("0.12"),
        Decimal("18400"),
        Decimal("1024"),
    }
    assert numbers_in("2x") != numbers_in("2")


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[]", '{"risks": "none"}', '{"risks": [{"type": "volume_spike"}]}', "null"],
)
def test_output_that_is_not_the_shape_asked_for_is_rejected(text: str) -> None:
    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, text)


def test_an_evidence_field_the_input_does_not_have_is_rejected() -> None:
    bad = risk("dmarc_policy_none") | {"evidence": ["checks.dmarc.strictness"]}

    with pytest.raises(InvalidOutputError):
        validate(SNAPSHOT, output(bad))


def test_an_empty_or_endless_title_or_reason_is_rejected() -> None:
    for bad in (
        risk("volume_spike", title=" "),
        risk("volume_spike", why=""),
        risk("volume_spike", title="x" * 121),
        risk("volume_spike", why="x" * 401),
    ):
        with pytest.raises(InvalidOutputError):
            validate(SNAPSHOT, output(bad))


def _fields(model: type[BaseModel], prefix: str = "") -> list[str]:
    found: list[str] = []
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            found += _fields(annotation, f"{prefix}{name}.")
        else:
            found.append(f"{prefix}{name}")
    return found


def test_the_evidence_fields_are_exactly_the_inputs_fields() -> None:
    assert sorted(EVIDENCE_FIELDS) == sorted(f for f in _fields(SnapshotInput) if f != "domain")


def test_the_schema_sent_to_the_model_is_closed() -> None:
    schema = ModelOutput.model_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["ModelRisk"]["additionalProperties"] is False
    assert sorted(schema["$defs"]["ModelRisk"]["required"]) == ["evidence", "title", "type", "why"]
    assert schema["$defs"]["RiskType"]["enum"] == [t.value for t in RiskType]
