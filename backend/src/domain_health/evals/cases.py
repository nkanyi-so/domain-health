"""An eval case: the exact input the model receives, and the label it is scored against."""

from pathlib import Path
from typing import Self

from pydantic import model_validator

from domain_health.models import Frozen, SnapshotInput
from domain_health.types import RiskType

HARD_PREFIX = "Hard:"


class Label(Frozen):
    """A type in none of the three lists is noise: it costs precision and is not harmful."""

    expected: list[RiskType]
    acceptable: list[RiskType]
    wrong: list[RiskType]

    @model_validator(mode="after")
    def lists_do_not_overlap(self) -> Self:
        every = [*self.expected, *self.acceptable, *self.wrong]
        repeated = sorted({t.value for t in every if every.count(t) > 1})
        if repeated:
            raise ValueError(f"a risk type is listed more than once: {repeated}")
        return self


class EvalCase(Frozen):
    input: SnapshotInput
    label: Label
    note: str

    @property
    def hard(self) -> bool:
        return self.note.startswith(HARD_PREFIX)


def load_cases(folder: Path) -> dict[str, EvalCase]:
    """Every case in the folder, keyed by file name without the extension, in name order."""
    cases: dict[str, EvalCase] = {}
    for path in sorted(folder.glob("*.json")):
        cases[path.stem] = EvalCase.model_validate_json(path.read_text(encoding="utf-8"))
    return cases
