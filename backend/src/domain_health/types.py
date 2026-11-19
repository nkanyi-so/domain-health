"""The two closed lists. `evals/RUBRIC.md` defines each entry and a test keeps the two equal.

A fix is a fault with one correct action, produced by a rule. A risk is a judgment call, ranked by
the model. The model may only return a `RiskType`; a risk's ID is built in code from it.
"""

from enum import StrEnum


class FixType(StrEnum):
    SPF_MISSING = "spf_missing"
    SPF_MULTIPLE = "spf_multiple"
    SPF_INVALID = "spf_invalid"
    SPF_TOO_MANY_LOOKUPS = "spf_too_many_lookups"
    SPF_PLUS_ALL = "spf_plus_all"
    DKIM_MISSING = "dkim_missing"
    DKIM_WEAK_KEY = "dkim_weak_key"
    DMARC_MISSING = "dmarc_missing"
    DMARC_INVALID = "dmarc_invalid"
    BLOCKLIST_LISTED = "blocklist_listed"
    COMPLAINT_RATE_OVER_LIMIT = "complaint_rate_over_limit"
    BOUNCE_RATE_OVER_LIMIT = "bounce_rate_over_limit"


class RiskType(StrEnum):
    DMARC_POLICY_NONE = "dmarc_policy_none"
    DMARC_PARTIAL_ENFORCEMENT = "dmarc_partial_enforcement"
    SPF_NEAR_LOOKUP_LIMIT = "spf_near_lookup_limit"
    SPF_WEAK_ALL = "spf_weak_all"
    DKIM_KEY_1024 = "dkim_key_1024"
    REPUTATION_DECLINING = "reputation_declining"
    REPUTATION_POOR = "reputation_poor"
    COMPLAINT_RATE_ELEVATED = "complaint_rate_elevated"
    BOUNCE_RATE_ELEVATED = "bounce_rate_elevated"
    VOLUME_SPIKE = "volume_spike"
    NEW_DOMAIN_VOLUME = "new_domain_volume"
    ENGAGEMENT_DECLINING = "engagement_declining"
    BLOCKLIST_RECENT = "blocklist_recent"
