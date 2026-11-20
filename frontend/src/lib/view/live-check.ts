// The live check: what each answer from the server means on the page, and the words for each
// refusal.

import type { LiveCheckResult } from "../api-types";
import { plural } from "./format";

/** The backend's names for why typed text is not a public domain name. */
export type RefusalReason =
  | "ip_address"
  | "single_label"
  | "too_long"
  | "reserved"
  | "internal"
  | "scheme"
  | "path"
  | "port"
  | "not_a_name";

export const REFUSAL_TITLE = "That is not a domain this can check";
export const NO_LOOKUP = "No lookup was made.";

const REFUSALS: Readonly<Record<RefusalReason, string>> = {
  ip_address: "That is an IP address. Type a domain name, like example.com.",
  single_label: "A domain name has at least two parts, like example.com.",
  too_long: "That is longer than a domain name can be (253 characters).",
  reserved: "That name is reserved, so no one can send mail from it.",
  internal: "That is an internal name, not a public domain.",
  scheme: "That is a web address. Leave out everything but the domain, like example.com.",
  path: "That is a web address. Leave out everything but the domain, like example.com.",
  port: "Leave out the port. Type the domain only, like example.com.",
  not_a_name: "That is not a domain name. Type one like example.com.",
};

/** The banner's second line for a refusal. A reason with no words of its own gets the last one. */
export function refusalMessage(reason: string): string {
  return Object.hasOwn(REFUSALS, reason) ? REFUSALS[reason as RefusalReason] : REFUSALS.not_a_name;
}

export type LiveCheckView =
  | { kind: "idle" }
  | { kind: "running"; domain: string }
  | { kind: "result"; result: LiveCheckResult; ageLine: string | null }
  | { kind: "refused"; domain: string; message: string }
  | { kind: "rate-limited" }
  | { kind: "cap-reached" }
  /** The backend cannot be reached: the check is switched off. */
  | { kind: "switched-off" }
  /** Anything else that went wrong on our side. */
  | { kind: "failed" };

/** "This result is 4 minutes old. Results are kept for ten minutes." Null for a fresh result. */
export function ageLine(result: LiveCheckResult, now: Date): string | null {
  if (!result.cached) {
    return null;
  }
  const minutes = Math.floor((now.getTime() - new Date(result.checked_at).getTime()) / 60_000);
  const age = minutes < 1 ? "less than a minute" : plural(minutes, "minute", "minutes");
  return `This result is ${age} old. Results are kept for ten minutes.`;
}

function field(body: unknown, name: string): unknown {
  return typeof body === "object" && body !== null ? (body as Record<string, unknown>)[name] : null;
}

/**
 * What the page shows for an answer from this site's own `/api/live-check` route:
 * 200 a result; 422 a refusal with its reason; 429 the address limit or the day's cap; 503 the
 * backend is away; anything else a failure.
 */
export function liveCheckView(
  status: number,
  body: unknown,
  typed: string,
  now: Date,
): LiveCheckView {
  if (status === 200 && typeof field(body, "domain") === "string") {
    const result = body as LiveCheckResult;
    return { kind: "result", result, ageLine: ageLine(result, now) };
  }
  if (status === 422) {
    const reason = field(body, "refused");
    return {
      kind: "refused",
      domain: typed,
      message: refusalMessage(typeof reason === "string" ? reason : ""),
    };
  }
  if (status === 429) {
    return field(body, "refused") === "daily_cap"
      ? { kind: "cap-reached" }
      : { kind: "rate-limited" };
  }
  if (status === 503) {
    return { kind: "switched-off" };
  }
  return { kind: "failed" };
}

/** What the live region says when a check comes back. */
export function finishedAnnouncement(result: LiveCheckResult): string {
  return result.fixes.length === 0
    ? "Check finished: nothing to fix."
    : `Check finished: ${plural(result.fixes.length, "fix", "fixes")}.`;
}

export function lookingUp(domain: string): string {
  return `Looking up DNS records for ${domain}.`;
}

/** Where a form leaves word, for this browser tab only, that the visitor pressed "Check domain". */
export const START_KEY = "dh-start-check";
/** How long a press stays good: long enough to open the check page, no longer. */
export const START_GOOD_FOR_MS = 30_000;

/** The two calls of the browser's session storage that the marker needs. */
export interface MarkerStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/** Leave word that the visitor pressed "Check domain" for this domain, now. */
export function leaveStart(store: MarkerStore, domain: string, now: number): void {
  store.setItem(START_KEY, JSON.stringify({ domain, at: now }));
}

/**
 * Should the check page start a check as it opens? Only when the visitor's own press of "Check
 * domain" on another page left a marker for exactly this domain a moment ago. An address alone
 * never starts one: a shared link, a prefetch or a crawler has no marker.
 */
export function shouldStart(marker: string | null, domain: string, now: number): boolean {
  if (marker === null || domain.trim() === "") {
    return false;
  }
  try {
    const left: unknown = JSON.parse(marker);
    if (typeof left !== "object" || left === null) {
      return false;
    }
    const { domain: asked, at } = left as { domain?: unknown; at?: unknown };
    return asked === domain && typeof at === "number" && now >= at && now - at < START_GOOD_FOR_MS;
  } catch {
    return false;
  }
}

/**
 * Take the marker, if this page is the one it was left for. A page with no domain does not look
 * at it or remove it: the check page draws a placeholder with no domain first, and a placeholder
 * that took the marker would leave nothing for the real page. A page with a domain removes
 * whatever marker it finds, so a press works once.
 */
export function takeStart(store: MarkerStore, domain: string, now: number): boolean {
  if (domain.trim() === "") {
    return false;
  }
  const marker = store.getItem(START_KEY);
  if (marker === null) {
    return false;
  }
  store.removeItem(START_KEY);
  return shouldStart(marker, domain, now);
}
