"""The model's output is untrusted: what is accepted, what is dropped, and who builds the ID."""

import contextlib
import json
from decimal import Decimal
from pathlib import Path

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
        "Volume rose x37 in a week.",
        "Complaints near \uff10.\uff17\uff17 percent.",
        "Complaints near \u0660.\u0667 percent.",
        "The limit is v9 of the policy.",
        "Sent 18K messages, a Q4 peak.",
        # What the page shows as 9000 or 420000, written so that it splits into known numbers.
        "Volume rose to 900\u200b0 messages.",
        "Volume rose to 900\u00ad0 messages.",
        "Volume rose to 42000\u20600 messages.",
        "Volume rose to 900\u03010 messages.",
        "Volume rose to 900 0 messages.",
        "Volume rose to 42 000 messages.",
        "Volume rose to 900\u2009000 messages.",
        "Open rate 31\u066b0\u066b4 percent.",
        "Volume rose to 900'000 messages.",
        "Volume rose to 900\u2019000 messages.",
        "Volume rose to 900\u00a0000 messages.",
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


def test_a_protocols_name_and_a_word_the_input_uses_are_not_numbers() -> None:
    assert numbers_in("spf1, DKIM1, sha256, IPv6 and p=none") == set()
    # A selector the input names, and the lists' own names, may be written.
    assert numbers_in("the key at s1", frozenset({"s1"})) == set()
    key = SNAPSHOT.checks.dkim.keys[0]
    named = f"The key at {key.selector}; see dkim_key_1024, volume_7d and listings_90d."
    assert len(validate(SNAPSHOT, output(risk("dkim_key_1024", why=named)))) == 1
    # Any other word that holds digits states them.
    assert numbers_in("x37 and v2") == {Decimal("37"), Decimal("2")}
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


def test_a_digit_led_word_in_the_input_does_not_excuse_invented_ones_in_the_output() -> None:
    key = SNAPSHOT.checks.dkim.keys[0].model_copy(update={"selector": "2024a"})
    dkim = SNAPSHOT.checks.dkim.model_copy(update={"keys": [key]})
    checks = SNAPSHOT.checks.model_copy(update={"dkim": dkim})
    odd = SNAPSHOT.model_copy(update={"checks": checks})

    for why in ("Complaints at 3x the limit.", "About 18k messages.", "Up 10x in a week."):
        with pytest.raises(InvalidOutputError, match="not in the input"):
            validate(odd, output(risk("complaint_rate_elevated", why=why)))


HOSTILE_TEXT = [
    "rate 1e1000000",
    "rate 1e999999999",
    "rate 9" * 60,
    "1E+9999999 and 0e-99999999",
    "1_000 or 1__0",
    "0x1F and 0b11 and 0o7",
    "1.",
    ".5",
    "1,,2",
    "1.2.3.4",
    "\u0661\u0662\u0663",
    "\uff11\uff12\uff13",
    "1e",
    "NaN and Infinity and -0",
    "1" + "0" * 300,
    "x" + "9" * 300,
    "\x00\x01 7",
    "7\u200b7",
    "\U0001d7cf\U0001d7d0\U0001d7d1",
    "\u2460\u2461\u2462",
    "\u00bd",
    "half a pair \ud800 here",
    "\udfff",
    "a tab\there",
    "a line\nbreak",
    "an escape \x1b[31m",
    "a zero-width\u200bjoiner and \u202e an override",
    "900\u200b0",
    "900\u00ad0 and 42000\u20600",
    "900 0",
    "42 000",
    "900\u2009000",
    "900\u3000000",
    "31\u066b0",
    "9\u20e3",
    "900\ufeff0",
    "0\u0338",
]


@pytest.mark.parametrize("why", HOSTILE_TEXT)
def test_no_text_the_model_can_write_makes_validation_raise_anything_else(why: str) -> None:
    """Model output is untrusted: whatever it holds, it is accepted or it is dropped."""
    text = output(risk("complaint_rate_elevated", why=why[:400]))

    with contextlib.suppress(InvalidOutputError):
        for accepted in validate(SNAPSHOT, text):
            # Whatever is accepted has to be usable: stored, sent and shown.
            accepted.model_dump_json().encode("utf-8")


@pytest.mark.parametrize(
    "bad", ["half a pair \ud800", "\udfff", "a tab\there", "two\nlines", "\x1b[31mred", "nul\x00"]
)
def test_a_character_that_cannot_be_stored_or_shown_drops_the_output(bad: str) -> None:
    for broken in (risk("volume_spike", why=bad), risk("volume_spike", title=bad)):
        with pytest.raises(InvalidOutputError, match="cannot be shown"):
            validate(SNAPSHOT, json.dumps({"risks": [broken]}))


def test_a_number_too_large_to_hold_is_dropped_and_leaves_the_caller_its_usual_error(
    tmp_path: Path,
) -> None:
    from domain_health.risks.model import RisksUnavailableError, risks_from
    from tests.eval_fixtures import recorded_call, write_prompt

    text = output(risk("complaint_rate_elevated", why="rate 1e1000000"))

    with pytest.raises(InvalidOutputError, match="not in the input"):
        validate(SNAPSHOT, text)
    call = recorded_call(write_prompt(tmp_path), SNAPSHOT, text)
    with pytest.raises(RisksUnavailableError, match="invalid output dropped"):
        risks_from(SNAPSHOT, call)


def test_case_06_holds_the_numbers_the_tricks_above_are_built_from() -> None:
    """The tricks only test anything if their pieces are numbers the input does hold."""
    from domain_health.risks import _numbers_of

    known = _numbers_of(SNAPSHOT.model_dump(mode="json"))

    assert {Decimal("900"), Decimal("0"), Decimal("42000")} <= known
    assert Decimal("9000") not in known
    assert Decimal("420000") not in known


def test_what_is_accepted_states_only_the_inputs_numbers_however_it_is_dressed() -> None:
    """For every hostile text that is accepted: strip everything invisible and every space
    between digits, and the numbers that are then on the page are still the input's."""
    import re
    import unicodedata

    from domain_health.risks import _numbers_of

    known = _numbers_of(SNAPSHOT.model_dump(mode="json"))
    for why in HOSTILE_TEXT:
        text = output(risk("complaint_rate_elevated", why=why[:400]))
        with contextlib.suppress(InvalidOutputError):
            for accepted in validate(SNAPSHOT, text):
                shown = unicodedata.normalize("NFKC", accepted.why)
                shown = "".join(c for c in shown if unicodedata.category(c)[0] not in "CM")
                joined = re.sub(r"(?<=[0-9])\s+(?=[0-9])", "", shown)
                assert numbers_in(joined) <= known, repr(why)


@pytest.mark.parametrize(
    "why",
    [
        "The 2048\u2011bit key is short.",
        "Volume went 40000\u201342000 messages.",
        "Volume went 40000-42000 messages.",
        "The \u20182048\u2019 key is short.",
        "Complaints 0.02, 900 days of history.",
        "The key is 2048. 900 days of history.",
        "Complaints at 0.02%; volume 42,000 (was 40,000).",
        "Volume: 42000/40000 this week against last.",
        "About 900\u00d7 nothing: just 900.",
        "Roughly \u00b10.02 either way.",
        "\u201c42000\u201d messages \u2014 900 days in.",
    ],
)
def test_ordinary_punctuation_around_the_inputs_numbers_is_accepted(why: str) -> None:
    """A dash of any kind, a quote mark, a list comma or a full stop beside a number is a
    sentence, not a disguise."""
    assert len(validate(SNAPSHOT, output(risk("complaint_rate_elevated", why=why)))) == 1


def test_case_06_holds_the_numbers_those_sentences_use() -> None:
    from domain_health.risks import _numbers_of

    known = _numbers_of(SNAPSHOT.model_dump(mode="json"))

    assert {Decimal(n) for n in ("2048", "40000", "42000", "0.02", "900")} <= known


# Generated, not listed by hand: every way of this kind to make the page show one number where
# the pieces are two numbers the input holds. Six review rounds found these one at a time.
def _whole_numbers() -> list[str]:
    from domain_health.risks import _numbers_of

    known = _numbers_of(SNAPSHOT.model_dump(mode="json"))
    return sorted(str(int(n)) for n in known if n == n.to_integral_value() and n >= 0)


def _joiners() -> list[str]:
    """Characters that put two runs of digits side by side for a reader: every format character
    and every space Unicode has, a sample of the combining marks, the apostrophes, and a comma."""
    import sys
    import unicodedata

    every = [chr(code) for code in range(sys.maxunicode + 1)]
    by_category = {
        category: [ch for ch in every if unicodedata.category(ch) == category]
        for category in ("Cf", "Zs", "Mn")
    }
    return [
        *by_category["Cf"],
        *by_category["Zs"],
        *by_category["Mn"][::40],
        "'",
        "`",
        "\u2019",
        ",",
        "",
    ]


def test_no_joiner_makes_two_of_the_inputs_numbers_pass_as_a_third() -> None:
    from domain_health.risks import _numbers_of

    known = _numbers_of(SNAPSHOT.model_dump(mode="json"))
    numbers = _whole_numbers()
    pairs = [(a, b) for a in numbers for b in numbers if Decimal(a + b) not in known and a != "0"]
    joiners = _joiners()
    assert len(pairs) >= 20
    assert len(joiners) >= 200
    passed = []
    for a, b in pairs:
        for joiner in joiners:
            why = f"Volume rose to {a}{joiner}{b} messages."
            with contextlib.suppress(InvalidOutputError):
                validate(SNAPSHOT, output(risk("volume_spike", why=why)))
                passed.append(why)

    assert passed == []


def test_full_width_digits_are_read_as_the_digits_they_show() -> None:
    wide = str.maketrans(
        "0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19"
    )
    for number in _whole_numbers():
        validate(SNAPSHOT, output(risk("volume_spike", why=f"It is {number.translate(wide)}.")))
        invented = (number + "7").translate(wide)
        with pytest.raises(InvalidOutputError, match="not in the input"):
            validate(SNAPSHOT, output(risk("volume_spike", why=f"It is {invented}.")))


def test_ordinary_separators_between_any_two_of_the_inputs_numbers_are_accepted() -> None:
    separators = [", ", ". ", "; ", ": ", " - ", "-", "\u2013", "\u2014", "/", " to ", " (", ") "]
    numbers = _whole_numbers()
    for a in numbers:
        for b in numbers:
            for separator in separators:
                why = f"Figures {a}{separator}{b} and so on."
                assert len(validate(SNAPSHOT, output(risk("volume_spike", why=why)))) == 1, why


@pytest.mark.parametrize(
    "why",
    ["A key of 20,48 bits.", "About 1,84,00 sent.", "Sent 18,4000.", "Sent 0,900.", "To 000,900."],
)
def test_a_comma_where_no_thousands_comma_goes_is_not_a_number(why: str) -> None:
    with pytest.raises(InvalidOutputError, match="not in the input"):
        validate(SNAPSHOT, output(risk("volume_spike", why=why)))
