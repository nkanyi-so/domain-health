"""What the risk model receives for one client on one day: checks, seeded sources and the fix list.

This shape is the `input` of every eval case in `evals/cases/`, so changing it changes the measure.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain_health.types import FixType

AllQualifier = Literal["-all", "~all", "?all", "+all"]
DmarcPolicy = Literal["none", "quarantine", "reject"]
ReputationGrade = Literal["high", "medium", "low", "bad"]
FixSource = Literal["dns", "seeded"]

# A domain younger than this has no earlier thirty-day window to compare its open rate with.
MIN_AGE_FOR_PREVIOUS_OPENS = 60


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SpfCheck(Frozen):
    present: bool
    record_count: int = Field(ge=0)
    # The next three are null when there is no single record to read.
    valid: bool | None
    lookup_count: int | None = Field(ge=0)
    all_qualifier: AllQualifier | None

    @model_validator(mode="after")
    def fields_agree(self) -> Self:
        if self.present != (self.record_count > 0):
            raise ValueError("spf: present must be true exactly when record_count is above 0")
        if self.record_count != 1:
            if (self.valid, self.lookup_count, self.all_qualifier) != (None, None, None):
                raise ValueError(
                    "spf: valid, lookup_count and all_qualifier need exactly one record"
                )
        elif self.valid is None:
            raise ValueError("spf: one record is either valid or not")
        elif self.valid and self.lookup_count is None:
            raise ValueError("spf: a valid record has a lookup count")
        elif not self.valid and (self.lookup_count, self.all_qualifier) != (None, None):
            raise ValueError("spf: a record that does not parse has no lookup count and no all")
        return self


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

    @model_validator(mode="after")
    def fields_agree(self) -> Self:
        if self.present != (self.valid is not None):
            raise ValueError("dmarc: valid is null exactly when no record was found")
        if self.valid:
            if self.policy is None or self.pct is None:
                raise ValueError(
                    "dmarc: a valid record has a policy and a pct (100 when it sets none)"
                )
        elif (self.policy, self.subdomain_policy, self.pct) != (None, None, None):
            raise ValueError("dmarc: policy, subdomain_policy and pct need a valid record")
        return self


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
    days_since_delisted: int | None = Field(ge=0, le=90)

    @model_validator(mode="after")
    def fields_agree(self) -> Self:
        if self.listed and self.listings_90d < 1:
            raise ValueError("blocklist: a current listing counts in listings_90d")
        if self.listed and self.days_since_delisted is not None:
            raise ValueError("blocklist: days_since_delisted is null while listed now")
        if not self.listed and (self.listings_90d > 0) != (self.days_since_delisted is not None):
            raise ValueError(
                "blocklist: when not listed now, days_since_delisted is set exactly when "
                "there was a listing in the last 90 days"
            )
        return self


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

    @model_validator(mode="after")
    def fields_agree(self) -> Self:
        if (self.open_rate_prev_pct is None) != (self.domain_age_days < MIN_AGE_FOR_PREVIOUS_OPENS):
            raise ValueError(
                "sources: open_rate_prev_pct is null exactly when the domain is under 60 days"
            )
        return self


class Fix(Frozen):
    type: FixType
    source: FixSource
    instruction: str


class SnapshotInput(Frozen):
    domain: str
    checks: Checks
    sources: Sources
    fixes: list[Fix]
