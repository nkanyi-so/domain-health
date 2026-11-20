// Signed session cookies. Two kinds: a visitor's, naming their sandbox, and the admin's.
//
// A cookie's value is `<kind>.<id>.<expiry in seconds>.<signature>`, where the signature is an
// HMAC-SHA256 of the first three parts under the session secret. Nothing in it is secret; it only
// has to be impossible to make without the key.

import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export type SessionKind = "visitor" | "admin";

export interface Session {
  kind: SessionKind;
  /** 32 hex characters. A visitor's names their sandbox. */
  id: string;
  /** Seconds since 1970. */
  expires: number;
}

export const VISITOR_COOKIE = "dh_session";
export const ADMIN_COOKIE = "dh_admin";

/** A visitor's cookie lasts a week; the sandbox it names resets a day after its first tick. */
export const VISITOR_SECONDS: number = 7 * 24 * 60 * 60;
/** An admin sign-in lasts twelve hours. */
export const ADMIN_SECONDS: number = 12 * 60 * 60;

const KIND_CODE: Record<SessionKind, string> = { visitor: "v", admin: "a" };
const ID = /^[0-9a-f]{32}$/;

function signature(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function newSessionId(): string {
  return randomBytes(16).toString("hex");
}

export function lifetime(kind: SessionKind): number {
  return kind === "admin" ? ADMIN_SECONDS : VISITOR_SECONDS;
}

/** A new session of this kind, starting now. */
export function startSession(kind: SessionKind, now: Date): Session {
  return { kind, id: newSessionId(), expires: Math.floor(now.getTime() / 1000) + lifetime(kind) };
}

export function sign(session: Session, secret: string): string {
  if (!secret) {
    throw new Error("no session secret");
  }
  const payload = `${KIND_CODE[session.kind]}.${session.id}.${session.expires}`;
  return `${payload}.${signature(payload, secret)}`;
}

/** The session a cookie value holds, or null: wrong kind, tampered, wrong key or expired. */
export function verify(
  value: string | undefined,
  kind: SessionKind,
  secret: string,
  now: Date,
): Session | null {
  if (!value || !secret) {
    return null;
  }
  const parts = value.split(".");
  if (parts.length !== 4) {
    return null;
  }
  const [code, id, expiry, given] = parts;
  const expected = Buffer.from(signature(`${code}.${id}.${expiry}`, secret));
  const got = Buffer.from(given);
  if (got.length !== expected.length || !timingSafeEqual(got, expected)) {
    return null;
  }
  if (code !== KIND_CODE[kind] || !ID.test(id) || !/^\d{1,12}$/.test(expiry)) {
    return null;
  }
  const expires = Number(expiry);
  if (expires * 1000 <= now.getTime()) {
    return null;
  }
  return { kind, id, expires };
}

export interface CookieOptions {
  httpOnly: true;
  sameSite: "lax";
  secure: boolean;
  path: "/";
  maxAge: number;
}

/** `Secure` everywhere except a local address reached over plain http. */
export function secureCookies(host: string | null, forwardedProto: string | null): boolean {
  const name = (host ?? "").replace(/:\d+$/, "").toLowerCase();
  const local = name === "localhost" || name === "127.0.0.1" || name === "[::1]";
  const proto = (forwardedProto ?? "").split(",")[0].trim().toLowerCase();
  return !(local && proto !== "https");
}

export function cookieOptions(secure: boolean, maxAge: number): CookieOptions {
  return { httpOnly: true, sameSite: "lax", secure, path: "/", maxAge };
}

/** Compares two secrets without the time taken saying how alike they are. */
export function sameSecret(given: string, expected: string, key: string): boolean {
  const a = createHmac("sha256", key).update(given).digest();
  const b = createHmac("sha256", key).update(expected).digest();
  return timingSafeEqual(a, b);
}
