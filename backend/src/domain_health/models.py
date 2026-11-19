"""What the risk model receives for one client on one day: checks, seeded sources and the fix list.

This shape is the `input` of every eval case in `evals/cases/`, so changing it changes the measure.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from domain_health.types import FixType

AllQualifier = Literal["-all", "~all", "?all", "+all"]
DmarcPolicy = Literal["none", "quarantine", "reject"]
ReputationGrade = Literal["high", "medium", "low", "bad"]
FixSource = Literal["dns", "seeded"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpfCheck(Frozen):
    present: bool
    record_count: int = Field(ge=0)
    # The next three are null when there is no single record to read.
    valid: bool | None
    lookup_count: int | None = Field(ge=0)
    all_qualifier: AllQualifier | None


class DkimKey(Frozen):
    selector: str
    key_bits: int = Field(gt=0)


class DkimCheck(Frozen):
    selectors_probed: int = Field(ge=0)
    keys: list[DkimKey]


class DmarcCheck(Frozen):
    present: bool
    # Null when no record was found; policy fields are also null when the record is invalid.
    valid: bool | None
    policy: DmarcPolicy | None
    subdomain_policy: DmarcPolicy | None
    pct: int | None = Field(ge=0, le=100)


class Checks(Frozen):
    spf: SpfCheck
    dkim: DkimCheck
    dmarc: DmarcCheck


class Reputation(Frozen):
    grade: ReputationGrade
    previous_grade: ReputationGrade


class Blocklist(Frozen):
    listed: bool
    listings_90d: int = Field(ge=0)
    # Days since the most recent listing ended; null when listed now or never listed in 90 days.
    days_since_delisted: int | None = Field(ge=0)


class Sources(Frozen):
    """Seeded on the demo: these come from accounts the demo does not have."""

    reputation: Reputation
    complaint_rate_pct: float = Field(ge=0, le=100)
    bounce_rate_pct: float = Field(ge=0, le=100)
    volume_7d: int = Field(ge=0)
    volume_prev_7d: int = Field(ge=0)
    open_rate_pct: float = Field(ge=0, le=100)
    # Null for a domain under 60 days old: there is no earlier thirty days to compare with.
    open_rate_prev_pct: float | None = Field(ge=0, le=100)
    blocklist: Blocklist
    domain_age_days: int = Field(ge=0)


class Fix(Frozen):
    type: FixType
    source: FixSource
    instruction: str


class SnapshotInput(Frozen):
    domain: str
    checks: Checks
    sources: Sources
    fixes: list[Fix]
