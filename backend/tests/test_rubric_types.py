"""The code's closed lists and the rubric's must be the same lists."""

import re

from domain_health.types import FixType, RiskType
from tests.paths import RUBRIC


def section(title: str) -> str:
    """The text under one `## ` heading of the rubric, up to the next one."""
    text = RUBRIC.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, f"the rubric has no section named {title!r}"
    return match.group(1)


def test_risk_types_in_code_equal_the_rubric() -> None:
    headings = re.findall(r"^### `([a-z0-9_]+)`$", section("Risk types"), re.MULTILINE)

    assert len(headings) == len(set(headings)), "a risk type is defined twice in the rubric"
    assert set(headings) == {t.value for t in RiskType}


def test_fix_types_in_code_equal_the_rubric() -> None:
    rows = re.findall(r"^\| `([a-z0-9_]+)` \|", section("Fix types"), re.MULTILINE)

    assert len(rows) == len(set(rows)), "a fix type is listed twice in the rubric"
    assert set(rows) == {t.value for t in FixType}


def test_no_name_is_both_a_fix_and_a_risk() -> None:
    assert not {t.value for t in FixType} & {t.value for t in RiskType}
