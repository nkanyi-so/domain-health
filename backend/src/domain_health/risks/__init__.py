"""The risk model's output: its shape, the rules it is held to, and the ID code gives each risk.

The model returns risk types from the closed list with its own wording. Everything else is
code's: the ID is `<type>:<domain>`, and output that breaks a rule is dropped whole, never
repaired. Model output is untrusted input.
"""

import json
import re
import unicodedata
from decimal import Decimal
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


# Unicode categories a title or reason may not hold: control characters and lone surrogates.
_UNUSABLE = frozenset({"Cc", "Cs"})


class InvalidOutputError(ValueError):
    """The model's output broke a rule. It is dropped whole."""


def risk_id(risk_type: RiskType, domain: str) -> str:
    """Identity is code's: the same type on the same domain is the same risk every day."""
    return f"{risk_type.value}:{domain}"


# A word is a run of letters, digits and underscores, with dots and commas inside it.
#
# - A word that starts with a digit is read as a number: 0.12, 18,000, 2048. If it is not one
#   (18k, 2x, 1.2.3, or 20,48 with its comma where no thousands comma goes) it is something
#   the input cannot hold, and counts as invented.
# - A word that starts with a letter and holds digits (x37, v2) is checked too: each run of digits
#   in it is a number, unless the whole word is one the input itself uses (a selector such as s1,
#   a field or type name) or a protocol's name.
# - Text is first folded to its plain form, so full-width digits are digits; a digit from any
#   other script cannot be in the input and counts as invented.
_WORD = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.,]*[A-Za-z0-9_])?")
_DIGITS = re.compile(r"[0-9]+")
_GROUPED = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")
NOT_A_NUMBER = Decimal("NaN")
PROTOCOL_WORDS = frozenset(
    {"spf1", "dkim1", "dmarc1", "ipv4", "ipv6", "ip4", "ip6", "sha1", "sha256"}
)


# Characters that take no room on the page: format characters (a zero-width space, a soft
# hyphen) and combining marks. Left in, they would split 9000 into 900 and 0 for the reader of
# this code and for nobody else.
_INVISIBLE = frozenset({"Cf", "Mn", "Me", "Mc"})
# Two digits with something between them that makes the page show one number where this code
# would read two: spaces only (9 000), an apostrophe (900'000), or a character outside ASCII
# that is not a dash (a separator or sign from another script). A dash between numbers is a
# range (40000-42000, with any kind of dash), and ordinary punctuation after a number (a comma
# and a space, a full stop, a quote mark) is just a sentence.
_BETWEEN_DIGITS = re.compile(r"(?<=[0-9])([^0-9A-Za-z.,_]+)(?=[0-9])")


def _joins_digits(gap: str) -> bool:
    if gap.isspace() or gap in ("'", "`"):
        return True
    return any(not ch.isascii() and unicodedata.category(ch) != "Pd" for ch in gap)


def _plain(text: str) -> str:
    """The text as the page shows it: compatibility forms folded, invisible characters gone."""
    folded = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in folded if unicodedata.category(ch) not in _INVISIBLE)


def words_in(text: str) -> set[str]:
    """Every word of a text, lower case: what the input's own text is made of."""
    return {word.lower() for word in _WORD.findall(_plain(text))}


def _number(word: str) -> Decimal:
    """A digit-led word as a number, or `NOT_A_NUMBER`. Never raises: a word such as 1e1000000
    is a number too large to hold, and that is not a number the input can hold either."""
    if "," in word and not _GROUPED.fullmatch(word):
        # 20,48 is not 2048: a comma inside a number only ever groups thousands.
        return NOT_A_NUMBER
    try:
        number = Decimal(word.replace(",", ""))
        return number.normalize() if number.is_finite() else NOT_A_NUMBER
    except ArithmeticError:
        return NOT_A_NUMBER


def numbers_in(text: str, known_words: frozenset[str] = frozenset()) -> set[Decimal]:
    """Every number a text states. `known_words` are letter-led words that may hold digits."""
    text = _plain(text)
    found: set[Decimal] = set()
    if any(ch.isdigit() and not ch.isascii() for ch in text) or any(
        _joins_digits(gap) for gap in _BETWEEN_DIGITS.findall(text)
    ):
        found.add(NOT_A_NUMBER)
    for word in _WORD.findall(text):
        if word[0].isdigit():
            found.add(_number(word))
        elif word.lower() not in known_words | PROTOCOL_WORDS:
            found |= {Decimal(digits).normalize() for digits in _DIGITS.findall(word)}
    return found


def _strings_of(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings_of(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings_of(item)]
    return []


def _numbers_of(value: object) -> set[Decimal]:
    """Every number an input holds, in its values and inside its text."""
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, int | float):
        return {Decimal(str(value)).normalize()}
    if isinstance(value, str):
        # A word in the input that starts with a digit and is not a number (a selector named
        # 2024a, say) is not a number the output may then match with any such word of its own.
        return numbers_in(value) - {NOT_A_NUMBER}
    if isinstance(value, dict):
        return set().union(*(_numbers_of(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_numbers_of(item) for item in value))
    return set()


# Names a risk's text may use that hold digits and are not the input's values: the closed lists
# and the input's field names.
NAMES = frozenset(
    {risk.value for risk in RiskType}
    | {part for field in EVIDENCE_FIELDS for part in field.split(".")}
    | {field.lower() for field in EVIDENCE_FIELDS}
)


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
    data = snapshot.model_dump(mode="json")
    known = _numbers_of(data)
    known_words = NAMES | frozenset(word for text in _strings_of(data) for word in words_in(text))
    for risk in output.risks:
        title, why = risk.title.strip(), risk.why.strip()
        if not title or not why:
            raise InvalidOutputError(f"{risk.type.value}: an empty title or reason")
        if len(title) > MAX_TITLE_CHARS or len(why) > MAX_WHY_CHARS:
            raise InvalidOutputError(f"{risk.type.value}: a title or reason that is too long")
        if any(unicodedata.category(ch) in _UNUSABLE for ch in title + why):
            # Half a surrogate pair cannot be stored or sent; a control character has no place
            # in a sentence shown to a person.
            raise InvalidOutputError(f"{risk.type.value}: a character that cannot be shown")
        if not numbers_in(f"{title} {why}", known_words) <= known:
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
