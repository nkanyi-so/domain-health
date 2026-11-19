"""The three DNS authentication checks and what each one found.

A check's `check` field is exactly the shape the risk model receives (`models.py`). What that
shape cannot say sits beside it: the records as read, the problems in plain words, and keys that
are not RSA.
"""

from domain_health.models import Checks, DkimCheck, DmarcCheck, Frozen, SpfCheck
from domain_health.resolver import TxtAnswer, TxtStatus


class LookupFailedError(Exception):
    """A lookup the check needed did not answer, so the check cannot say anything."""


def records_at(name: str, answer: TxtAnswer) -> tuple[str, ...]:
    """The records a lookup gave, all of them. Silence, or more text than a check reads, is not
    "no record": the check that asked cannot be made."""
    if answer.status is TxtStatus.TIMEOUT:
        raise LookupFailedError(f"the lookup of {name} did not answer")
    if answer.status is TxtStatus.TOO_LARGE:
        raise LookupFailedError(f"the lookup of {name} gave more text than a check reads")
    return answer.records


class Unavailable(Frozen):
    """The check could not be made. Never read as "no record"."""

    reason: str


class SpfFinding(Frozen):
    check: SpfCheck
    records: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


class DkimFinding(Frozen):
    check: DkimCheck
    # Selectors holding a key that is not RSA (Ed25519). `key_bits` is an RSA length, so these
    # are found, never called weak, and kept out of `check.keys`.
    other_keys: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


class DmarcFinding(Frozen):
    check: DmarcCheck
    record: str | None = None
    # The name the record was found at: the domain itself, or a parent whose policy it inherits.
    found_at: str | None = None
    problems: tuple[str, ...] = ()


class CheckResults(Frozen):
    domain: str
    spf: SpfFinding | Unavailable
    dkim: DkimFinding | Unavailable
    dmarc: DmarcFinding | Unavailable

    @property
    def unavailable(self) -> list[str]:
        named = (("spf", self.spf), ("dkim", self.dkim), ("dmarc", self.dmarc))
        return [name for name, found in named if isinstance(found, Unavailable)]

    def model_input(self) -> Checks:
        """The checks as the risk model receives them. Every check has to have been made."""
        if (
            isinstance(self.spf, Unavailable)
            or isinstance(self.dkim, Unavailable)
            or isinstance(self.dmarc, Unavailable)
        ):
            raise LookupFailedError(f"not checked: {', '.join(self.unavailable)}")
        return Checks(spf=self.spf.check, dkim=self.dkim.check, dmarc=self.dmarc.check)
