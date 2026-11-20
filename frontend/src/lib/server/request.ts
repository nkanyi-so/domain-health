// What a request says about where it came from: its origin and the visitor's address.

import { isIP } from "node:net";

export interface HeaderBag {
  get(name: string): string | null;
}

export const LOCAL_ADDRESS = "127.0.0.1";

/**
 * True when the `Origin` header names the host the request itself was sent to. A write with no
 * `Origin`, or one from any other site, is refused.
 */
export function sameOrigin(origin: string | null, host: string | null): boolean {
  if (!origin || !host) {
    return false;
  }
  let parsed: URL;
  try {
    parsed = new URL(origin);
  } catch {
    return false;
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return false;
  }
  return parsed.host.toLowerCase() === host.trim().toLowerCase();
}

function oneAddress(text: string | null | undefined): string | null {
  const candidate = (text ?? "").trim();
  // An address with a zone ("fe80::1%eth0") is not a public address, and the backend refuses it.
  return candidate && !candidate.includes("%") && isIP(candidate) !== 0 ? candidate : null;
}

/**
 * The visitor's address as the platform reports it: exactly one IP address, never a list.
 * The first entry of `x-forwarded-for` (the platform writes it), then `x-real-ip`. With neither,
 * as on a local machine, the local address: every such caller then shares one limit.
 */
export function clientAddress(headers: HeaderBag): string {
  const forwarded = headers.get("x-forwarded-for");
  const first = forwarded === null ? null : forwarded.split(",")[0];
  return oneAddress(first) ?? oneAddress(headers.get("x-real-ip")) ?? LOCAL_ADDRESS;
}
