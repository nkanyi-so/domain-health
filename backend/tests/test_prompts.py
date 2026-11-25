"""What a prompt version may not hold (docs/EVALS.md, "What the prompt says"): the rubric's
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


def test_quoting_means_six_words_in_a_row_and_a_full_stop_is_not_a_word() -> None:
    line = "- **Expected:** `grade` is `low` or `bad`."
    assert line in band_lines()
    assert prompt_rules.words(line) == ["expected", "grade", "is", "low", "or", "bad"]
    assert prompt_rules.words("checks.spf.valid is 0.10, e.g. this.") == [
        "checks.spf.valid", "is", "0.10", "e.g", "this",
    ]  # fmt: skip

    # Five words the line also uses, then a full stop: not a quote.
    assert problems_with("Raise it when the grade is low or bad. Otherwise do not.") == []
    # Six of the line's words in a row: a quote.
    assert problems_with("Expected: grade is low or bad.") != []


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


def test_wording_that_places_a_line_relative_to_a_figure_is_listed_not_judged() -> None:
    text = (
        "Recall the cap.\n- The count equals the cap exactly, or is a single lookup short of it: "
        "raise.\n- A count of half the cap or less: not raised.\nReturn the list. Twice is twice."
    )

    listed = prompt_rules.relative_wording(text)

    assert listed == [
        "Recall the cap.",
        "The count equals the cap exactly, or is a single lookup short of it: raise.",
        "A count of half the cap or less: not raised.",
        "Twice is twice.",
    ]
    assert prompt_rules.relative_wording("Rank the risks a specialist would raise.") == []
    # It is a list for a reader: the same text has no problem under the rules.
    assert problems_with(text) == []


def test_version_three_is_listed_for_the_wording_a_challenge_named() -> None:
    v3 = load_prompt(PROMPTS / "risks-v3.md").text

    listed = " ".join(prompt_rules.relative_wording(v3))

    for phrase in ("a single lookup short of it", "half the cap or less", "twice that length"):
        assert phrase in listed


def test_version_four_is_listed_for_the_sentence_that_takes_a_length_from_a_field_name() -> None:
    v4 = load_prompt(PROMPTS / "risks-v4.md").text

    listed = prompt_rules.relative_wording(v4)

    assert any("The name of `listings_90d` gives its length in days." in s for s in listed)
    assert any("exactly a third of the lookback window" in s for s in listed)
    assert any("Recall that count." in s for s in listed)
