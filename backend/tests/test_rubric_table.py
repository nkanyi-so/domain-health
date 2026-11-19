"""The cases against `evals/RUBRIC.md` read as a table (`domain_health.evals.table`).

A "table" case's label must be exactly what the bands give. An "open" case's label must differ
from the bands somewhere, or it is not open. Every case's fix list must be what the fix table
gives. Part of the measure: the owner changes this file.
"""

import pytest

from domain_health.evals.cases import EvalCase, Label, load_cases
from domain_health.evals.table import baseline_risks, fix_types, table_label
from domain_health.types import RiskType
from tests.paths import CASES

CASES_BY_NAME = load_cases(CASES)
NAMES = list(CASES_BY_NAME)


def as_sets(label: Label) -> tuple[set[RiskType], set[RiskType], set[RiskType]]:
    return set(label.expected), set(label.acceptable), set(label.wrong)


@pytest.mark.parametrize("name", NAMES)
def test_the_fix_list_is_what_the_fix_table_gives(name: str) -> None:
    case = CASES_BY_NAME[name]

    assert [fix.type for fix in case.input.fixes] == fix_types(case.input)


@pytest.mark.parametrize("name", [n for n in NAMES if CASES_BY_NAME[n].set == "table"])
def test_a_table_case_is_labelled_as_the_bands_give(name: str) -> None:
    case = CASES_BY_NAME[name]

    assert as_sets(case.label) == as_sets(table_label(case.input))


@pytest.mark.parametrize("name", [n for n in NAMES if CASES_BY_NAME[n].set == "open"])
def test_an_open_case_departs_from_the_bands(name: str) -> None:
    case = CASES_BY_NAME[name]

    assert as_sets(case.label) != as_sets(table_label(case.input))
    assert case.note.startswith("Open:")


def test_every_type_is_placed_at_most_once_by_the_bands() -> None:
    for case in CASES_BY_NAME.values():
        table_label(case.input)  # Label refuses a type in two bands


def test_the_baseline_returns_what_the_bands_expect() -> None:
    case: EvalCase = CASES_BY_NAME["20-five-at-once"]

    assert set(baseline_risks(case.input)) == set(case.label.expected)
    assert len(baseline_risks(case.input)) == 5


def test_the_baseline_is_silent_on_a_healthy_domain() -> None:
    assert baseline_risks(CASES_BY_NAME["01-healthy-baseline"].input) == []
