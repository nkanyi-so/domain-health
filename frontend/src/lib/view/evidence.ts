// The fields a risk says it is based on, in plain words.

import type { RiskEvidence } from "../api-types";

const SPF = "the SPF record";
const DKIM = "the DKIM keys";
const DMARC = "the DMARC record";
const REPUTATION = "reputation grade";
const VOLUME = "weekly volume";
const OPEN_RATE = "open rate";
const BLOCKLIST = "blocklist history";

// Every field name the API can send has its words here: a new one fails the type check.
export const EVIDENCE_WORDS: Readonly<Record<RiskEvidence, string>> = {
  "checks.spf.present": SPF,
  "checks.spf.record_count": SPF,
  "checks.spf.valid": SPF,
  "checks.spf.lookup_count": SPF,
  "checks.spf.all_qualifier": SPF,
  "checks.dkim.selectors_probed": DKIM,
  "checks.dkim.keys": DKIM,
  "checks.dmarc.present": DMARC,
  "checks.dmarc.valid": DMARC,
  "checks.dmarc.policy": DMARC,
  "checks.dmarc.subdomain_policy": DMARC,
  "checks.dmarc.pct": DMARC,
  "sources.reputation.grade": REPUTATION,
  "sources.reputation.previous_grade": REPUTATION,
  "sources.complaint_rate_pct": "complaint rate",
  "sources.bounce_rate_pct": "bounce rate",
  "sources.volume_7d": VOLUME,
  "sources.volume_prev_7d": VOLUME,
  "sources.open_rate_pct": OPEN_RATE,
  "sources.open_rate_prev_pct": OPEN_RATE,
  "sources.blocklist.listed": BLOCKLIST,
  "sources.blocklist.listings_90d": BLOCKLIST,
  "sources.blocklist.days_since_delisted": BLOCKLIST,
  "sources.domain_age_days": "domain age",
  fixes: "the fix list",
};

/** A field's plain words, or its own name when it has none. */
export function evidenceWords(field: string): string {
  return Object.hasOwn(EVIDENCE_WORDS, field) ? EVIDENCE_WORDS[field as RiskEvidence] : field;
}

/** The fields with no plain words: shown by their own names. A test lists any. */
export function unnamedEvidence(fields: readonly string[]): string[] {
  return [...new Set(fields.filter((field) => !Object.hasOwn(EVIDENCE_WORDS, field)))];
}

/** "Based on: the DMARC record, weekly volume": each thing said once, in the order given. */
export function basedOn(evidence: readonly string[]): string {
  const words = [...new Set(evidence.map(evidenceWords))];
  return `Based on: ${words.join(", ")}`;
}
