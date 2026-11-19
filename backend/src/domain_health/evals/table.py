"""`evals/RUBRIC.md` read as a table: the fix types and the label its bands give for one input.

Three uses, all in the evals:

- a test re-derives every "table" case's label and every case's fix list, so a hand edit of a case
  or of the rubric cannot drift;
- the rules-only baseline: what a threshold table with no model returns, scored beside the model;
- a check that recorded output for the seeded clients names no type the rubric calls wrong.

It is never an input to the model, a prompt or the daily pipeline: if it were, the eval would be
measuring this file. It does not know the "open" cases, where the label is a written call.
"""

from domain_health.evals.cases import Label
from domain_health.models import ReputationGrade, SnapshotInput
from domain_health.types import FixType, RiskType

LOOKUP_LIMIT = 10
LOW_VOLUME = 1000
WORST_TO_BEST: tuple[ReputationGrade, ...] = ("bad", "low", "medium", "high")
STRICTNESS = {"none": 0, "quarantine": 1, "reject": 2}


def fix_types(snapshot: SnapshotInput) -> list[FixType]:
    """The rubric's "Fix types" table, in the table's order."""
    spf, dkim, dmarc = snapshot.checks.spf, snapshot.checks.dkim, snapshot.checks.dmarc
    sources = snapshot.sources
    found: list[FixType] = []
    if not spf.present:
        found.append(FixType.SPF_MISSING)
    elif spf.record_count > 1:
        found.append(FixType.SPF_MULTIPLE)
    elif not spf.valid:
        found.append(FixType.SPF_INVALID)
    else:
        if spf.lookup_count is not None and spf.lookup_count > LOOKUP_LIMIT:
            found.append(FixType.SPF_TOO_MANY_LOOKUPS)
        if spf.all_qualifier == "+all":
            found.append(FixType.SPF_PLUS_ALL)
    if not dkim.keys:
        found.append(FixType.DKIM_MISSING)
    elif any(key.key_bits < 1024 for key in dkim.keys):
        found.append(FixType.DKIM_WEAK_KEY)
    if not dmarc.present:
        found.append(FixType.DMARC_MISSING)
    elif not dmarc.valid:
        found.append(FixType.DMARC_INVALID)
    if sources.blocklist.listed:
        found.append(FixType.BLOCKLIST_LISTED)
    if sources.complaint_rate_pct >= 0.30:
        found.append(FixType.COMPLAINT_RATE_OVER_LIMIT)
    if sources.bounce_rate_pct >= 5.0:
        found.append(FixType.BOUNCE_RATE_OVER_LIMIT)
    return found


class Bands:
    """Collects each risk type into the band the rubric gives it. A type left out is noise."""

    def __init__(self) -> None:
        self.expected: list[RiskType] = []
        self.acceptable: list[RiskType] = []
        self.wrong: list[RiskType] = []

    def label(self) -> Label:
        return Label(expected=self.expected, acceptable=self.acceptable, wrong=self.wrong)


def _dmarc(snapshot: SnapshotInput, auth_fix_open: bool, bands: Bands) -> None:
    dmarc, age = snapshot.checks.dmarc, snapshot.sources.domain_age_days
    if not dmarc.valid or dmarc.policy is None or dmarc.pct is None:
        bands.wrong += [RiskType.DMARC_POLICY_NONE, RiskType.DMARC_PARTIAL_ENFORCEMENT]
        return
    if dmarc.policy == "none":
        ready = age >= 90 and not auth_fix_open
        (bands.expected if ready else bands.acceptable).append(RiskType.DMARC_POLICY_NONE)
        bands.wrong.append(RiskType.DMARC_PARTIAL_ENFORCEMENT)
        return
    bands.wrong.append(RiskType.DMARC_POLICY_NONE)
    subdomain = dmarc.subdomain_policy
    full = dmarc.pct == 100 and (
        subdomain is None or STRICTNESS[subdomain] >= STRICTNESS[dmarc.policy]
    )
    if full:
        bands.wrong.append(RiskType.DMARC_PARTIAL_ENFORCEMENT)
    elif dmarc.pct < 100 or subdomain == "none":
        bands.expected.append(RiskType.DMARC_PARTIAL_ENFORCEMENT)
    elif dmarc.policy == "reject" and subdomain == "quarantine":
        bands.acceptable.append(RiskType.DMARC_PARTIAL_ENFORCEMENT)


def _spf(snapshot: SnapshotInput, bands: Bands) -> None:
    spf, dmarc = snapshot.checks.spf, snapshot.checks.dmarc
    if spf.record_count != 1 or not spf.valid or spf.lookup_count is None:
        bands.wrong += [RiskType.SPF_NEAR_LOOKUP_LIMIT, RiskType.SPF_WEAK_ALL]
        return
    lookups = spf.lookup_count
    if lookups > LOOKUP_LIMIT or lookups <= 5:
        bands.wrong.append(RiskType.SPF_NEAR_LOOKUP_LIMIT)
    elif lookups >= 9:
        bands.expected.append(RiskType.SPF_NEAR_LOOKUP_LIMIT)
    elif lookups == 8:
        bands.acceptable.append(RiskType.SPF_NEAR_LOOKUP_LIMIT)

    enforcing = bool(dmarc.valid) and dmarc.policy in ("quarantine", "reject")
    if spf.all_qualifier in ("-all", "+all"):
        bands.wrong.append(RiskType.SPF_WEAK_ALL)
    elif spf.all_qualifier == "~all" or enforcing:
        bands.acceptable.append(RiskType.SPF_WEAK_ALL)
    else:
        bands.expected.append(RiskType.SPF_WEAK_ALL)


def _dkim(snapshot: SnapshotInput, bands: Bands) -> None:
    bits = [key.key_bits for key in snapshot.checks.dkim.keys]
    if not bits or any(b < 1024 for b in bits) or all(b >= 2048 for b in bits):
        bands.wrong.append(RiskType.DKIM_KEY_1024)
    elif all(b < 2048 for b in bits):
        bands.expected.append(RiskType.DKIM_KEY_1024)
    else:
        bands.acceptable.append(RiskType.DKIM_KEY_1024)


def _reputation(snapshot: SnapshotInput, bands: Bands) -> None:
    reputation = snapshot.sources.reputation
    dropped = WORST_TO_BEST.index(reputation.grade) < WORST_TO_BEST.index(reputation.previous_grade)
    (bands.expected if dropped else bands.wrong).append(RiskType.REPUTATION_DECLINING)
    if reputation.grade in ("low", "bad"):
        bands.expected.append(RiskType.REPUTATION_POOR)
    elif reputation.grade == "medium":
        bands.acceptable.append(RiskType.REPUTATION_POOR)
    else:
        bands.wrong.append(RiskType.REPUTATION_POOR)


def _rates(snapshot: SnapshotInput, bands: Bands) -> None:
    sources = snapshot.sources
    low_volume = sources.volume_7d < LOW_VOLUME
    at_volume = bands.acceptable if low_volume else bands.expected

    complaints = sources.complaint_rate_pct
    if complaints >= 0.30 or complaints < 0.05:
        bands.wrong.append(RiskType.COMPLAINT_RATE_ELEVATED)
    elif complaints >= 0.10:
        at_volume.append(RiskType.COMPLAINT_RATE_ELEVATED)
    elif complaints >= 0.08:
        bands.acceptable.append(RiskType.COMPLAINT_RATE_ELEVATED)

    bounces = sources.bounce_rate_pct
    if bounces >= 5.0 or bounces < 1.0:
        bands.wrong.append(RiskType.BOUNCE_RATE_ELEVATED)
    elif bounces >= 2.0:
        at_volume.append(RiskType.BOUNCE_RATE_ELEVATED)
    elif bounces >= 1.5:
        bands.acceptable.append(RiskType.BOUNCE_RATE_ELEVATED)

    previous = sources.open_rate_prev_pct
    if previous is None or previous == 0:
        return
    fall = (previous - sources.open_rate_pct) / previous
    if fall < 0.05:
        bands.wrong.append(RiskType.ENGAGEMENT_DECLINING)
    elif fall >= 0.20:
        at_volume.append(RiskType.ENGAGEMENT_DECLINING)
    elif fall >= 0.10:
        bands.acceptable.append(RiskType.ENGAGEMENT_DECLINING)


def _volume(snapshot: SnapshotInput, bands: Bands) -> None:
    sources = snapshot.sources
    age, now, before = sources.domain_age_days, sources.volume_7d, sources.volume_prev_7d
    # A previous week of 0 with mail this week counts as a ratio of 2.0 or more.
    ratio = now / before if before else (2.0 if now else 0.0)
    if ratio < 1.2:
        bands.wrong.append(RiskType.VOLUME_SPIKE)
    elif ratio >= 2.0:
        absorbs = age >= 365 and sources.reputation.grade == "high"
        (bands.acceptable if absorbs else bands.expected).append(RiskType.VOLUME_SPIKE)
    elif ratio >= 1.5:
        bands.acceptable.append(RiskType.VOLUME_SPIKE)

    if age >= 180:
        bands.wrong.append(RiskType.NEW_DOMAIN_VOLUME)
    elif age < 30:
        (bands.expected if now > 5000 else bands.acceptable).append(RiskType.NEW_DOMAIN_VOLUME)
    elif age < 90 and now > 5000:
        bands.acceptable.append(RiskType.NEW_DOMAIN_VOLUME)


def _blocklist(snapshot: SnapshotInput, bands: Bands) -> None:
    blocklist = snapshot.sources.blocklist
    recent = blocklist.days_since_delisted is not None and blocklist.days_since_delisted <= 30
    if blocklist.listed or blocklist.listings_90d == 0:
        bands.wrong.append(RiskType.BLOCKLIST_RECENT)
    elif recent or blocklist.listings_90d >= 2:
        bands.expected.append(RiskType.BLOCKLIST_RECENT)
    else:
        bands.acceptable.append(RiskType.BLOCKLIST_RECENT)


def table_label(snapshot: SnapshotInput) -> Label:
    """The label the rubric's bands give: wrong first, then expected, then acceptable."""
    bands = Bands()
    fixes = fix_types(snapshot)
    auth_fix_open = any(fix.value.startswith(("spf_", "dkim_")) for fix in fixes)
    _dmarc(snapshot, auth_fix_open, bands)
    _spf(snapshot, bands)
    _dkim(snapshot, bands)
    _reputation(snapshot, bands)
    _rates(snapshot, bands)
    _volume(snapshot, bands)
    _blocklist(snapshot, bands)
    return bands.label()


def baseline_risks(snapshot: SnapshotInput) -> list[RiskType]:
    """The rules-only baseline: every type the bands expect, in the rubric's order, no model."""
    expected = set(table_label(snapshot).expected)
    return [risk for risk in RiskType if risk in expected]
