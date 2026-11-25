"""What a prompt version may not hold (docs/EVALS.md, "What the prompt says"): the rubric's
numbers, its band lines, or anything taken from an eval case.

The same check runs in two places: as a test on every version file, and in the paid command
before the first call, so that a prompt that breaks a rule is never paid for.
"""

import json
import re
from collections.abc import Iterable

from domain_health.models import SnapshotInput
from domain_health.risks import NAMES, numbers_in
from domain_health.risks.model import input_hash

SHINGLE = 6  # words in a row


def words(text: str) -> list[str]:
    """Words in lower case. A dot inside a word is part of it (`checks.spf.valid`, `0.10`);
    punctuation by itself is not a word."""
    return re.findall(r"[a-z0-9_%]+(?:\.[a-z0-9_%]+)*", text.lower())


def shingles(text: str) -> set[tuple[str, ...]]:
    found = words(text)
    return {tuple(found[i : i + SHINGLE]) for i in range(len(found) - SHINGLE + 1)}


def rubric_rules(rubric: str) -> str:
    """The part of the rubric that holds the thresholds and the bands."""
    return rubric[rubric.index("## The input") : rubric.index("## How a case is labelled")]


def band_lines(rubric: str) -> list[str]:
    return [
        line
        for line in rubric_rules(rubric).splitlines()
        if line.startswith(("- **Expected:**", "- **Acceptable:**", "- **Wrong:**"))
    ]


def problems_with(prompt_text: str, rubric: str, inputs: Iterable[SnapshotInput]) -> list[str]:
    """Everything in a prompt that the rules for the paid runs forbid. Empty when it is clean."""
    found: list[str] = []
    # The closed lists' names and the input's field names hold digits and are not thresholds.
    quoted = numbers_in(prompt_text, NAMES) & numbers_in(rubric_rules(rubric), NAMES)
    if quoted:
        found.append(f"numbers from the rubric: {sorted(str(n) for n in quoted)}")
    prompt_shingles = shingles(prompt_text)
    for line in band_lines(rubric):
        shared = shingles(line) & prompt_shingles
        if shared:
            found.append(f"quotes a band line ({' '.join(sorted(shared)[0])}): {line[:60]}")
    inputs = list(inputs)
    for snapshot in inputs:
        if snapshot.domain in prompt_text:
            found.append(f"names an eval case's domain: {snapshot.domain}")
    hashes = {input_hash(snapshot) for snapshot in inputs}
    for block in re.findall(r"```(?:json)?\n(.*?)```", prompt_text, flags=re.DOTALL):
        try:
            example = SnapshotInput.model_validate(json.loads(block))
        except ValueError:
            continue
        if input_hash(example) in hashes:
            found.append("a worked example is an eval case's input")
    return found


# Words that place a line by arithmetic on a figure instead of stating the figure: "half the
# cap", "twice that length", "a single lookup short of it".
_RELATIVE = re.compile(
    r"\b(half|twice|double|multiple|several times|several-fold|times larger|"
    r"short of|exactly|fraction of|a few hundred|thousands of|"
    # Version 4 also leans on the input's own field names and on plain spans of time.
    r"a third of|a month|full year|ordinary year|lookback window|the thousands|the hundreds|"
    r"bulk-sender count|name of|gives its length|recall)\b",
    re.IGNORECASE,
)


def relative_wording(prompt_text: str) -> list[str]:
    """The sentences of a prompt that place a line relative to a figure the model is asked to
    recall, a field's name or a span of time. Wording relative to a public figure is
    allowed (2026-11-19) as long as it is shown; the rest is listed so that it can be judged. This
    lists it for a reader, and nothing passes or fails on it. The list is by words, so it can
    include a sentence that is not a threshold and miss one phrased another way."""
    # Not split at a colon: a term and the sentence that defines it stay together.
    sentences = re.split(r"(?<=[.?!])\s+|\n+", prompt_text)
    found = [" ".join(sentence.split()) for sentence in sentences if _RELATIVE.search(sentence)]
    return list(dict.fromkeys(sentence.lstrip("- ").strip() for sentence in found))
