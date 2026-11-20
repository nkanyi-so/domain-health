// "What was checked": each DNS check's status in words, its problems and its records as read.

import type {
  CheckResults,
  DkimFinding,
  DmarcFinding,
  Fix,
  SpfFinding,
  Unavailable,
} from "../api-types";

export type CheckName = "SPF" | "DKIM" | "DMARC";
export type CheckState = "ok" | "problem" | "not-made";

export interface CheckRow {
  name: CheckName;
  state: CheckState;
  /** "Found, no problems", "Problem found" or "Check not made". */
  words: string;
  /** Plain words after "Problem found", or why the check was not made. */
  notes: string[];
  /** The records as read, shown in the well. Untrusted text: only ever rendered as text. */
  records: string[];
  /** A line under the records, such as where a DMARC record was found. */
  foundAt: string | null;
}

const WORDS: Record<CheckState, string> = {
  ok: "Found, no problems",
  problem: "Problem found",
  "not-made": "Check not made",
};

const FIX_PREFIX: Record<CheckName, string> = { SPF: "spf_", DKIM: "dkim_", DMARC: "dmarc_" };

function isUnavailable(finding: object): finding is Unavailable {
  return "reason" in finding;
}

function notMade(name: CheckName, finding: Unavailable): CheckRow {
  const timedOut = finding.reason.includes("did not answer");
  const why = timedOut
    ? "The lookup did not answer in time, so nothing is assumed. No fix is listed for it."
    : "The check could not be finished, so nothing is assumed. No fix is listed for it.";
  return {
    name,
    state: "not-made",
    words: WORDS["not-made"],
    notes: [why],
    records: [],
    foundAt: null,
  };
}

function row(
  name: CheckName,
  fixes: readonly Fix[],
  missing: string | null,
  problems: readonly string[],
  records: string[],
  foundAt: string | null = null,
): CheckRow {
  const notes = [...(missing ? [missing] : []), ...problems.map(sentence)];
  const hasFix = fixes.some((fix) => fix.type.startsWith(FIX_PREFIX[name]));
  const state: CheckState = notes.length > 0 || hasFix ? "problem" : "ok";
  return { name, state, words: WORDS[state], notes, records, foundAt };
}

/** A problem as the check wrote it, made to read as a sentence. */
function sentence(text: string): string {
  const trimmed = text.trim();
  // A problem that opens with the record's own text ("p=monitor is not ...") keeps its case: a
  // tag is written in lower case in the record, and "P=monitor" is not what was read.
  const quotesRecord = /^[a-z0-9_]+[=:]/.test(trimmed);
  const capital = quotesRecord ? trimmed : trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capital) ? capital : `${capital}.`;
}

function spf(finding: SpfFinding, fixes: readonly Fix[]): CheckRow {
  const missing = finding.check.present ? null : "No SPF record was found.";
  return row("SPF", fixes, missing, finding.problems ?? [], [...(finding.records ?? [])]);
}

function dkim(finding: DkimFinding, fixes: readonly Fix[]): CheckRow {
  const keys = finding.check.keys.map(
    (key) => `${key.selector}._domainkey: RSA key, ${key.key_bits} bits`,
  );
  const others = (finding.other_keys ?? []).map(
    (selector) => `${selector}._domainkey: a key that is not RSA`,
  );
  const found = keys.length + others.length > 0;
  const missing = found
    ? null
    : `No DKIM key was found at the ${finding.check.selectors_probed} common selectors probed.`;
  return row("DKIM", fixes, missing, finding.problems ?? [], [...keys, ...others]);
}

function dmarc(finding: DmarcFinding, fixes: readonly Fix[]): CheckRow {
  const missing = finding.check.present ? null : "No DMARC record was found.";
  const records = finding.record ? [finding.record] : [];
  const foundAt = finding.found_at && finding.record ? `Found at ${finding.found_at}` : null;
  return row("DMARC", fixes, missing, finding.problems ?? [], records, foundAt);
}

export function checkRows(checks: CheckResults, fixes: readonly Fix[]): CheckRow[] {
  return [
    isUnavailable(checks.spf) ? notMade("SPF", checks.spf) : spf(checks.spf, fixes),
    isUnavailable(checks.dkim) ? notMade("DKIM", checks.dkim) : dkim(checks.dkim, fixes),
    isUnavailable(checks.dmarc) ? notMade("DMARC", checks.dmarc) : dmarc(checks.dmarc, fixes),
  ];
}

/** "From DNS" or "From seeded figures". */
export function fixSource(fix: Fix): string {
  return fix.source === "dns" ? "From DNS" : "From seeded figures";
}
