"""The rules engine: check results and seeded data in, the fix list out. No model.

A fix is a fault with one correct action: true or false whatever else is going on. Each rule reads
one fact. A check that could not be made gives no fix, and neither do sources that are absent (a
typed domain has none).
"""

from domain_health.models import DkimCheck, DmarcCheck, Fix, FixSource, Sources, SpfCheck
from domain_health.types import FixType

SPF_LOOKUP_LIMIT = 10
DKIM_MIN_KEY_BITS = 1024
COMPLAINT_LIMIT_PCT = 0.30
BOUNCE_LIMIT_PCT = 5.0

_SEEDED = {
    FixType.BLOCKLIST_LISTED,
    FixType.COMPLAINT_RATE_OVER_LIMIT,
    FixType.BOUNCE_RATE_OVER_LIMIT,
}

INSTRUCTIONS: dict[FixType, str] = {
    FixType.SPF_MISSING: (
        "Publish an SPF record for this domain that lists every service that sends its mail."
    ),
    FixType.SPF_MULTIPLE: (
        "Merge the SPF records into one: receivers treat more than one as an error."
    ),
    FixType.SPF_INVALID: "Correct the SPF record's syntax so that it parses.",
    FixType.SPF_TOO_MANY_LOOKUPS: (
        "Reduce the SPF record to 10 DNS lookups or fewer by removing or flattening includes."
    ),
    FixType.SPF_PLUS_ALL: (
        "Replace +all in the SPF record with ~all or -all: "
        "+all lets any server send as this domain."
    ),
    FixType.DKIM_MISSING: (
        "Publish a DKIM key for this domain, or tell us the selector in use: "
        "none was found at the common selectors."
    ),
    FixType.DKIM_WEAK_KEY: (
        "Rotate the DKIM key to 2,048 bits: a key under 1,024 bits is rejected by receivers."
    ),
    FixType.DMARC_MISSING: (
        "Publish a DMARC record for this domain, starting at p=none with a reporting address."
    ),
    FixType.DMARC_INVALID: "Correct the DMARC record's syntax so that it parses.",
    FixType.BLOCKLIST_LISTED: "Fix the cause of the blocklist listing, then request delisting.",
    FixType.COMPLAINT_RATE_OVER_LIMIT: (
        "Stop the mail stream that is drawing complaints and remove the people who complained: "
        "the rate is over the 0.30% limit."
    ),
    FixType.BOUNCE_RATE_OVER_LIMIT: (
        "Stop sending to this list and validate it: the bounce rate is over the 5% limit."
    ),
}


def source_of(fix_type: FixType) -> FixSource:
    return "seeded" if fix_type in _SEEDED else "dns"


def _spf(spf: SpfCheck) -> list[FixType]:
    if spf.record_count == 0:
        return [FixType.SPF_MISSING]
    if spf.record_count > 1:
        return [FixType.SPF_MULTIPLE]
    if not spf.valid:
        return [FixType.SPF_INVALID]
    found: list[FixType] = []
    if spf.lookup_count is not None and spf.lookup_count > SPF_LOOKUP_LIMIT:
        found.append(FixType.SPF_TOO_MANY_LOOKUPS)
    if spf.all_qualifier == "+all":
        found.append(FixType.SPF_PLUS_ALL)
    return found


def _dkim(dkim: DkimCheck, other_dkim_keys: int) -> list[FixType]:
    if not dkim.keys:
        # A key that is not RSA is still a key: it has no RSA length, so it is never weak here.
        return [] if other_dkim_keys else [FixType.DKIM_MISSING]
    if min(key.key_bits for key in dkim.keys) < DKIM_MIN_KEY_BITS:
        return [FixType.DKIM_WEAK_KEY]
    return []


def _dmarc(dmarc: DmarcCheck) -> list[FixType]:
    if not dmarc.present:
        return [FixType.DMARC_MISSING]
    return [] if dmarc.valid else [FixType.DMARC_INVALID]


def _seeded(sources: Sources) -> list[FixType]:
    found: list[FixType] = []
    if sources.blocklist.listed:
        found.append(FixType.BLOCKLIST_LISTED)
    if sources.complaint_rate_pct >= COMPLAINT_LIMIT_PCT:
        found.append(FixType.COMPLAINT_RATE_OVER_LIMIT)
    if sources.bounce_rate_pct >= BOUNCE_LIMIT_PCT:
        found.append(FixType.BOUNCE_RATE_OVER_LIMIT)
    return found


def fix_list(
    spf: SpfCheck | None,
    dkim: DkimCheck | None,
    dmarc: DmarcCheck | None,
    sources: Sources | None,
    *,
    other_dkim_keys: int = 0,
) -> list[Fix]:
    """Every fix that is true of this data, in the closed list's order. `None` is "not known"."""
    found: list[FixType] = []
    if spf is not None:
        found += _spf(spf)
    if dkim is not None:
        found += _dkim(dkim, other_dkim_keys)
    if dmarc is not None:
        found += _dmarc(dmarc)
    if sources is not None:
        found += _seeded(sources)
    return [Fix(type=t, source=source_of(t), instruction=INSTRUCTIONS[t]) for t in found]
