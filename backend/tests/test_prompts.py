"""What a prompt version may not hold (docs/SPEC.md, "Rules for the paid runs"): the rubric's
numbers, its band lines, or anything taken from an eval case. Every version file is checked."""

from pathlib import Path

import pytest

from domain_health.evals.cases import load_cases
from domain_health.risks import numbers_in, prompt_rules
from domain_health.risks.prompt import load_prompt, prompt_versions, unversioned
from domain_health.types import FixType, RiskType
from tests.paths import CASES, REPO, RUBRIC

PROMPTS = REPO / "prompts"
VERSIONS = prompt_versions(PROMPTS)
RUBRIC_TEXT = RUBRIC.read_text(encoding="utf-8")
INPUTS = [case.input for case in load_cases(CASES).values()]


def problems_with(prompt_text: str) -> list[str]:
    return prompt_rules.problems_with(prompt_text, RUBRIC_TEXT, INPUTS)


def rubric_rules() -> str:
    return prompt_rules.rubric_rules(RUBRIC_TEXT)


def band_lines() -> list[str]:
    return prompt_rules.band_lines(RUBRIC_TEXT)


def test_the_rubric_has_numbers_and_band_lines_to_keep_out() -> None:
    assert len(numbers_in(rubric_rules())) > 20
    # Thirteen risk types, each with two or three bands.
    assert 30 <= len(band_lines()) <= 39


def test_the_check_catches_each_kind_of_leak() -> None:
    case = load_cases(CASES)["06-dmarc-none-established"]
    clean = "Rank the risks a specialist would raise. Return at most eight."

    assert problems_with(clean) == []
    assert problems_with(clean + " Flag complaints from 0.10 up.") != []
    assert problems_with(clean + " A domain at least 90 days old.") != []
    assert problems_with(clean + " " + band_lines()[0]) != []
    assert problems_with(clean + f" For example {case.input.domain}.") != []
    example = "\n```json\n" + case.input.model_dump_json() + "\n```\n"
    assert any("worked example" in p for p in problems_with(clean + example))
    # A type's name is not a number from the rubric.
    assert problems_with(clean + " Use dkim_key_1024 for an old key.") == []
    # The same input under another domain is no longer that case, but its figures still sit on
    # the rubric's lines: a worked example has to stay clear of those too.
    made_up = case.input.model_copy(update={"domain": "made-up.example"})
    moved = problems_with(clean + "\n```json\n" + made_up.model_dump_json() + "\n```\n")
    assert len(moved) == 1
    assert moved[0].startswith("numbers from the rubric")


def test_the_prompts_folder_holds_only_version_files() -> None:
    assert unversioned(PROMPTS) == []


@pytest.mark.parametrize("path", VERSIONS, ids=[path.name for path in VERSIONS])
def test_a_prompt_version_holds_nothing_from_the_rubrics_bands_or_the_cases(path: Path) -> None:
    assert problems_with(load_prompt(path).text) == []


@pytest.mark.parametrize("path", VERSIONS, ids=[path.name for path in VERSIONS])
def test_a_prompt_version_names_every_risk_type_and_asks_for_no_fix(path: Path) -> None:
    text = load_prompt(path).text

    assert [risk.value for risk in RiskType if risk.value not in text] == []
    # Fixes are the rules' and reach the model as input; the prompt has no list of them to pick.
    assert [fix.value for fix in FixType if f"`{fix.value}`" in text] == []
