"""The numbers in the README and in docs/EVALS.md are the result files' numbers.

Their generated parts equal what `make readme` makes today, every "N in 144" in them is the count
the results file holds for whoever the sentence is about, the claim and its limit stand word for
word in docs/EVALS.md and on the page, and the README opens with the finding.
"""

import json
import re
from typing import Any

import pytest

from domain_health.readme_tables import (
    BOUNDARIES,
    EVALS,
    EVALS_PARTS,
    README,
    README_PARTS,
    RESULTS,
    ReadmeError,
    attempts,
    blocks,
    eval_table,
    in_readme,
    main,
    render,
    v4_boundaries,
)
from tests.paths import REPO

# The claim's quoted line and its limit are kept in docs/EVALS.md.
CLAIM_FILE = EVALS

SECTIONS = (
    "## The point",
    "## How it works",
    "## Results",
    "## Run it",
    "## Production notes",
    "## How it was built",
    "## Next",
)


def results() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(RESULTS.read_text(encoding="utf-8"))
    return loaded


def readme() -> str:
    assert README == REPO / "README.md"
    assert README.exists(), "README.md is missing"
    return README.read_text(encoding="utf-8")


def evals_doc() -> str:
    assert EVALS == REPO / "docs" / "EVALS.md"
    assert EVALS.exists(), "docs/EVALS.md is missing"
    return EVALS.read_text(encoding="utf-8")


def shown(text: str) -> str:
    """Text with runs of whitespace as one space, so a wrapped line still matches."""
    return " ".join(text.split())


@pytest.fixture(scope="module")
def made() -> dict[str, str]:
    return blocks()


# (a) The generated parts and the files they are written from cannot differ.


def test_every_generated_part_of_the_readme_and_the_evals_doc_is_current(
    made: dict[str, str],
) -> None:
    assert sorted(made) == [
        "eval-attempts",
        "eval-sets",
        "eval-table",
        "prompt-wording",
        "v4-boundaries",
        "v4-wording",
    ]
    assert README_PARTS == ("eval-table",)
    assert sorted(EVALS_PARTS) == sorted(made)
    for path, text, names in (
        ("README.md", readme(), README_PARTS),
        ("docs/EVALS.md", evals_doc(), EVALS_PARTS),
    ):
        for name in names:
            assert in_readme(text, name) == made[name], (
                f"{path}'s `{name}` part is out of date: run `make readme` and commit the file"
            )
        assert render(text, {name: made[name] for name in names}) == text


def test_the_table_names_the_prompt_the_model_and_the_date_of_the_results_file(
    made: dict[str, str],
) -> None:
    source, table = results(), made["eval-table"]

    assert f"Prompt in use: `{source['prompt_version']}`" in table
    assert f"Model: `{source['model']}`" in table
    assert f"Run recorded {source['recorded_at'][:10]}" in table
    assert f"{int(source['measures']['harmful']['value'])} in {source['case_runs']} case-runs" in (
        table
    )


def test_the_table_marks_as_missed_exactly_the_bars_the_results_file_says_are_missed(
    made: dict[str, str],
) -> None:
    source = results()
    missed = [name for name, one in source["measures"].items() if not one["met"]]
    in_use = next(
        line for line in made["eval-table"].splitlines() if line.startswith("| Model, prompt in")
    )

    assert missed, "no bar is missed any more: the README's words about the miss are now false"
    assert in_use.endswith(f"| **no: {' and '.join(missed)} missed** |")
    assert in_use.count("missed**") == len(missed) + 1


def test_the_table_follows_the_results_file_when_a_number_in_it_changes() -> None:
    source = results()
    rules_only = {"coverage": 0.9, "precision": 1.0, "harmful": 0.0, "stability": 1.0}
    source["measures"]["harmful"]["value"] = 0.0
    source["measures"]["harmful"]["met"] = True
    source["measures"]["stability"]["value"] = 0.5
    source["measures"]["stability"]["met"] = False

    table = eval_table(source, rules_only)

    assert "| 0 in 144 case-runs (48 cases, 3 runs whose first five agreed on 24), met |" in table
    assert "**0.500 (24 of 48 cases), missed**" in table
    assert "**no: stability missed**" in table


def test_a_results_file_whose_met_disagrees_with_its_bar_stops_the_command() -> None:
    source = results()
    source["measures"]["harmful"]["met"] = True

    with pytest.raises(ReadmeError, match="disagrees with its bar"):
        eval_table(source, {"coverage": 1.0, "precision": 1.0, "harmful": 0.0, "stability": 1.0})


def test_the_attempts_scored_from_the_recordings_agree_with_the_results_file() -> None:
    source, rows = results(), attempts()
    by_name = {(row["prompt"], row["model"]): row for row in rows}

    assert [(row["prompt"], row["model"]) for row in rows] == [
        ("risks-v1", "gpt-6-luna"),
        ("risks-v2", "gpt-6-luna"),
        ("risks-v3", "gpt-6-luna"),
        ("risks-v3", "gpt-6.1-terra"),
        ("risks-v4", "gpt-6.1-terra"),
    ]
    in_use = by_name[(source["prompt_version"], source["model"])]
    for name in ("coverage", "precision", "harmful", "stability"):
        assert in_use[name] == pytest.approx(source["measures"][name]["value"])
    assert in_use["missed"] == [n for n, one in source["measures"].items() if not one["met"]]
    assert in_use["cost_usd"] == pytest.approx(source["cost_usd"])
    for other in source["not_in_use"]:
        row = by_name[(other["prompt_version"], source["model"])]
        for name in ("coverage", "precision", "harmful", "stability"):
            assert row[name] == pytest.approx(other[name])
    assert {row["case_runs"] for row in rows} == {source["case_runs"]}
    assert {row["calls"] for row in rows} == {source["case_runs"]}


def test_every_boundary_sentence_is_one_the_results_file_lists_for_version_4() -> None:
    source = results()
    listed = next(
        other["prompt_relative_wording"]
        for other in source["not_in_use"]
        if other["prompt_version"] == "risks-v4"
    )
    part = v4_boundaries(source)
    sentences = [line[4:] for line in part.splitlines() if line.startswith("  - ")]

    assert len(sentences) == sum(len(markers) for _, _, markers in BOUNDARIES)
    assert len(set(sentences)) == len(sentences)
    for sentence in sentences:
        assert sentence in listed


def test_a_boundary_the_results_file_no_longer_holds_stops_the_command() -> None:
    source = results()
    source["not_in_use"][0]["prompt_relative_wording"] = ["Recall the cap."]

    with pytest.raises(ReadmeError, match="sentences of risks-v4"):
        v4_boundaries(source)


def test_the_command_rewrites_only_what_is_between_the_markers(tmp_path: Any) -> None:
    target, also = tmp_path / "README.md", tmp_path / "EVALS.md"
    stale = re.sub(r"\b9 in 144 case-runs, missed", "0 in 144 case-runs, missed", readme())
    stale_evals = re.sub(
        r"\b9 in 144 case-runs, missed", "0 in 144 case-runs, missed", evals_doc(), count=1
    )
    assert stale != readme()
    assert stale_evals != evals_doc()
    target.write_text(stale, encoding="utf-8")
    also.write_text(stale_evals, encoding="utf-8")

    assert main(target, also) == 0
    assert target.read_text(encoding="utf-8") == readme()
    assert also.read_text(encoding="utf-8") == evals_doc()


def test_a_missing_or_repeated_marker_stops_the_command() -> None:
    with pytest.raises(ReadmeError, match="0 times"):
        in_readme("no markers here", "eval-table")
    twice = "<!-- a:start -->\nx\n<!-- a:end -->\n<!-- a:start -->\ny\n<!-- a:end -->\n"
    with pytest.raises(ReadmeError, match="2 times"):
        in_readme(twice, "a")


# (b) Every "N in 144" is the results file's count for whoever the sentence is about.


def subjects(source: dict[str, Any]) -> list[tuple[str, int]]:
    """Each way the README names someone the results file holds a harmful count for, as a
    pattern, with that count: the prompt in use, each version not in use, and the baseline."""

    def version(name: str) -> str:
        number = name.removeprefix("risks-v")
        assert number.isdigit(), name
        return rf"\bversion {number}\b|\b{re.escape(name)}\b"

    in_use = int(source["measures"]["harmful"]["value"])
    assert in_use == source["measures"]["harmful"]["value"]
    assert in_use == sum(one["harmful"] for one in source["sets"].values())
    found = [(version(source["prompt_version"]) + r"|\bprompt in use\b", in_use)]
    for other in source["not_in_use"]:
        pattern = version(other["prompt_version"])
        if len(source["not_in_use"]) == 1:
            pattern += r"|\bfinal attempt\b"
        found.append((pattern, int(other["harmful"])))
    baseline = sum(one["baseline_harmful"] for one in source["sets"].values())
    found.append((r"\bbaseline\b|\brules-only\b|\btable of rules\b", baseline))
    return found


def wrong_counts(text: str, source: dict[str, Any]) -> list[str]:
    """Every "N in <case-runs>" that is not the results file's count for the nearest thing named
    before it on its line, or that has nothing named before it."""
    case_runs = int(source["case_runs"])
    assert case_runs == source["cases"] * source["runs"]
    named = subjects(source)
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in re.finditer(rf"\b(\d+) in {case_runs}\b", line):
            before = line[: match.start()]
            nearest: tuple[int, int] | None = None
            for pattern, count in named:
                ends = [found.end() for found in re.finditer(pattern, before, re.IGNORECASE)]
                if ends and (nearest is None or max(ends) > nearest[0]):
                    nearest = (max(ends), count)
            if nearest is None:
                problems.append(f"line {number}: `{match[0]}` names no one the results file holds")
            elif int(match[1]) != nearest[1]:
                problems.append(
                    f"line {number}: `{match[0]}`, but the results file holds {nearest[1]}"
                )
    return problems


def test_every_n_in_144_in_the_readme_and_the_evals_doc_is_the_results_files_count() -> None:
    source = results()

    for text, at_least in ((readme(), 3), (evals_doc(), 5)):
        assert len(re.findall(rf"\b\d+ in {source['case_runs']}\b", text)) >= at_least
        assert wrong_counts(text, source) == []


def test_the_count_check_sees_a_wrong_count_and_a_count_about_no_one() -> None:
    source = results()
    in_use = int(source["measures"]["harmful"]["value"])
    other = int(source["not_in_use"][0]["harmful"])
    assert len({in_use, other, 0}) == 3

    assert wrong_counts(f"Version 3 returned {in_use} in 144 case-runs.", source) == []
    assert wrong_counts(f"`risks-v4` gave {other} in 144; the baseline 0 in 144.", source) == []
    assert wrong_counts(f"Version 3 had {in_use} in 144, version 4 {other} in 144.", source) == []
    assert len(wrong_counts("Version 3 returned 0 in 144 case-runs.", source)) == 1
    assert len(wrong_counts(f"Version 4 returned {in_use} in 144.", source)) == 1
    assert len(wrong_counts(f"The rules-only baseline: {in_use} in 144.", source)) == 1
    assert len(wrong_counts(f"It scored {in_use} in 144 case-runs.", source)) == 1
    assert len(wrong_counts(f"Version 3\nreturned {in_use} in 144.", source)) == 1
    assert (
        len(wrong_counts(f"Version 3 had {in_use} in 144, the final attempt 13 in 144.", source))
        == 1
    )


# (c) The claim and its limit, word for word, and the finding the README opens with.


def claim() -> str:
    quoted: list[str] = re.findall(
        r"^> (.+)$", CLAIM_FILE.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert len(quoted) == 1
    return quoted[0].strip()


def limit() -> str:
    """The limit as docs/EVALS.md has it beside the claim: it starts lower case, inside a longer
    sentence, and ends at its closing bracket."""
    found: list[str] = re.findall(
        r"(on this project's evals a table of rules does better[^\n]*?to its none\))",
        evals_doc(),
    )
    assert len(found) == 1
    return found[0]


FINDING = (
    "I built the eval before the prompt. It showed that a plain table of rules beats the model at "
    "choosing which risks to raise, so the product ships the rules for the action list and shows "
    "the model's picks beside it, marked advisory. Knowing when not to use a model was the result."
)
FRONTEND_CLAIM = REPO / "frontend" / "src" / "content" / "claim.ts"
FRONTEND_LIMIT = REPO / "frontend" / "src" / "content" / "limit.ts"


def test_the_evals_doc_states_the_limit_beside_the_claim() -> None:
    """The claim and its limit stand together in docs/EVALS.md: the limit once, after the claim
    and before the next section."""
    text, sentence = evals_doc(), limit()

    assert text.count(claim()) == 1
    after_claim = text[text.index(claim()) + len(claim()) :]
    assert sentence in after_claim[: after_claim.index("\n## ")]


def test_the_page_states_the_claim_and_its_limit_word_for_word() -> None:
    sentence = limit()
    as_a_sentence = sentence[0].upper() + sentence[1:] + "."

    assert claim() in shown(FRONTEND_CLAIM.read_text(encoding="utf-8"))
    assert shown(FRONTEND_LIMIT.read_text(encoding="utf-8")).count(as_a_sentence) == 1


def test_the_readme_opens_with_the_finding_before_the_first_section() -> None:
    text = shown(readme())

    assert text.count(FINDING) == 1
    assert text.index(FINDING) < text.index(shown(SECTIONS[0]))


# The sections.


def test_the_seven_sections_are_there_in_order() -> None:
    headings = [line for line in readme().splitlines() if line.startswith("## ")]

    assert headings == list(SECTIONS)
