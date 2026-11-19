"""The risk model's output: its shape, the rules it is held to, and the ID code gives each risk.

The model returns risk types from the closed list with its own wording. Everything else is
code's: the ID is `<type>:<domain>`, and output that breaks a rule is dropped whole, never
repaired. Model output is untrusted input.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Literal, get_args

from pydantic import ValidationError

from domain_health.models import Frozen, SnapshotInput
from domain_health.types import RiskType

MAX_RISKS = 8
MAX_TITLE_CHARS = 120
MAX_WHY_CHARS = 400

# The input fields a risk may point at as its evidence. A test keeps this equal to the fields of
# `SnapshotInput`, so the model can never name a field that does not exist.
EvidenceField = Literal[
    "checks.spf.present",
    "checks.spf.record_count",
    "checks.spf.valid",
    "checks.spf.lookup_count",
    "checks.spf.all_qualifier",
    "checks.dkim.selectors_probed",
    "checks.dkim.keys",
    "checks.dmarc.present",
    "checks.dmarc.valid",
    "checks.dmarc.policy",
    "checks.dmarc.subdomain_policy",
    "checks.dmarc.pct",
    "sources.reputation.grade",
    "sources.reputation.previous_grade",
    "sources.complaint_rate_pct",
    "sources.bounce_rate_pct",
    "sources.volume_7d",
    "sources.volume_prev_7d",
    "sources.open_rate_pct",
    "sources.open_rate_prev_pct",
    "sources.blocklist.listed",
    "sources.blocklist.listings_90d",
    "sources.blocklist.days_since_delisted",
    "sources.domain_age_days",
    "fixes",
]
EVIDENCE_FIELDS: tuple[str, ...] = get_args(EvidenceField)


class ModelRisk(Frozen):
    """One risk as the model returns it."""

    type: RiskType
    title: str
    why: str
    evidence: list[EvidenceField]


class ModelOutput(Frozen):
    """The structured output asked of the model: its risks, most important first."""

    risks: list[ModelRisk]


class Risk(Frozen):
    """A risk after validation, with the ID code built for it."""

    id: str
    type: RiskType
    title: str
    why: str
    evidence: list[EvidenceField]


class InvalidOutputError(ValueError):
    """The model's output broke a rule. It is dropped whole."""


def risk_id(risk_type: RiskType, domain: str) -> str:
    """Identity is code's: the same type on the same domain is the same risk every day."""
    return f"{risk_type.value}:{domain}"


# A word is a run of letters, digits and underscores, with dots and commas inside it. A word that
# starts with a digit is read as a number: 0.12, 18,000, 2048. One that starts with a letter is
# not (spf1, s1, DKIM1). A word that starts with a digit and is not a number (18k, 2x, 1.2.3) is
# something the input cannot hold, and counts as invented.
_WORD = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.,]*[A-Za-z0-9_])?")
NOT_A_NUMBER = Decimal("NaN")


def numbers_in(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for word in _WORD.findall(text):
        if not word[0].isdigit():
            continue
        try:
            number = Decimal(word.replace(",", ""))
        except InvalidOperation:
            number = NOT_A_NUMBER
        found.add(number.normalize() if number.is_finite() else NOT_A_NUMBER)
    return found


def _numbers_of(value: object) -> set[Decimal]:
    """Every number an input holds, in its values and inside its text."""
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, int | float):
        return {Decimal(str(value)).normalize()}
    if isinstance(value, str):
        return numbers_in(value)
    if isinstance(value, dict):
        return set().union(*(_numbers_of(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_numbers_of(item) for item in value))
    return set()


def validate(snapshot: SnapshotInput, output_text: str) -> list[Risk]:
    """The model's raw output as a ranked list of risks, or `InvalidOutputError`.

    The rules, from the spec: a known type, no duplicate, at most eight, and every number in a
    risk's text present in the input. One broken rule drops the whole output.
    """
    try:
        output = ModelOutput.model_validate(json.loads(output_text))
    except (ValueError, ValidationError) as error:
        raise InvalidOutputError(f"not the shape asked for: {type(error).__name__}") from error
    if len(output.risks) > MAX_RISKS:
        raise InvalidOutputError(f"{len(output.risks)} risks, more than {MAX_RISKS}")
    types = [risk.type for risk in output.risks]
    if len(set(types)) != len(types):
        raise InvalidOutputError("a risk type appears twice")
    known = _numbers_of(snapshot.model_dump(mode="json"))
    for risk in output.risks:
        title, why = risk.title.strip(), risk.why.strip()
        if not title or not why:
            raise InvalidOutputError(f"{risk.type.value}: an empty title or reason")
        if len(title) > MAX_TITLE_CHARS or len(why) > MAX_WHY_CHARS:
            raise InvalidOutputError(f"{risk.type.value}: a title or reason that is too long")
        if not numbers_in(f"{title} {why}") <= known:
            raise InvalidOutputError(f"{risk.type.value}: a number that is not in the input")
    return [
        Risk(
            id=risk_id(risk.type, snapshot.domain),
            type=risk.type,
            title=risk.title.strip(),
            why=risk.why.strip(),
            evidence=risk.evidence,
        )
        for risk in output.risks
    ]
