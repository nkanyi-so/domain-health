"""The cases load in the documented shape and have the mix the plan and the spec ask for.

Nothing here judges a label: whether a label is right is the rubric's and the owner's call.
"""

import json
import tomllib

import pytest
from pydantic import ValidationError

from domain_health.evals.cases import EvalCase, Label, load_cases
from domain_health.types import RiskType
from tests.paths import BARS, CASES

CASES_BY_NAME = load_cases(CASES)


TABLE = {name: case for name, case in CASES_BY_NAME.items() if case.set == "table"}
OPEN = {name: case for name, case in CASES_BY_NAME.items() if case.set == "open"}


def test_forty_cases_load() -> None:
    assert len(CASES_BY_NAME) == 40


def test_ten_cases_are_open_and_named_so() -> None:
    assert len(OPEN) == 10
    assert all("-open-" in name for name in OPEN)
    assert not any("-open-" in name for name in TABLE)


def test_file_names_are_numbered_in_order() -> None:
    numbers = [int(name.split("-", 1)[0]) for name in CASES_BY_NAME]

    assert numbers == list(range(1, 41))


def test_at_least_six_cases_are_hard() -> None:
    assert sum(case.hard for case in CASES_BY_NAME.values()) >= 6


def test_at_least_four_cases_are_healthy() -> None:
    healthy = [c for c in CASES_BY_NAME.values() if not c.label.expected and not c.input.fixes]

    assert len(healthy) >= 4


@pytest.mark.parametrize("risk_type", list(RiskType))
def test_every_risk_type_is_expected_at_least_twice_and_wrong_somewhere(
    risk_type: RiskType,
) -> None:
    labels = [case.label for case in CASES_BY_NAME.values()]

    assert sum(risk_type in label.expected for label in labels) >= 2
    assert any(risk_type in label.wrong for label in labels)


def test_no_case_expects_more_than_the_five_that_are_scored() -> None:
    assert all(len(case.label.expected) <= 5 for case in CASES_BY_NAME.values())


def test_every_domain_is_invented_and_used_once() -> None:
    domains = [case.input.domain for case in CASES_BY_NAME.values()]

    assert all(domain.endswith(".example") for domain in domains)
    assert len(domains) == len(set(domains))


def test_every_case_says_why() -> None:
    assert all(len(case.note) >= 40 for case in CASES_BY_NAME.values())


def test_a_fix_type_appears_once_per_case() -> None:
    for name, case in CASES_BY_NAME.items():
        types = [fix.type for fix in case.input.fixes]
        assert len(types) == len(set(types)), name


def test_a_type_cannot_be_in_two_label_lists() -> None:
    with pytest.raises(ValidationError):
        Label(expected=[RiskType.VOLUME_SPIKE], acceptable=[], wrong=[RiskType.VOLUME_SPIKE])


def test_an_unknown_field_in_a_case_is_refused() -> None:
    raw = json.loads((CASES / "01-healthy-baseline.json").read_text(encoding="utf-8"))
    raw["input"]["checks"]["spf"]["surprise"] = 1

    with pytest.raises(ValidationError):
        EvalCase.model_validate(raw)


def test_an_unknown_risk_type_in_a_label_is_refused() -> None:
    raw = json.loads((CASES / "01-healthy-baseline.json").read_text(encoding="utf-8"))
    raw["label"]["expected"] = ["made_up_risk"]

    with pytest.raises(ValidationError):
        EvalCase.model_validate(raw)


def test_the_bars_file_has_the_four_measures() -> None:
    bars = tomllib.loads(BARS.read_text(encoding="utf-8"))

    assert set(bars) == {"coverage", "precision", "harmful", "stability"}
    assert all({"op", "value"} <= set(bar) for bar in bars.values())
