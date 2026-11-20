import { describe, expect, it } from "vitest";
import {
  ADMIN_SECONDS,
  VISITOR_SECONDS,
  cookieOptions,
  newSessionId,
  sameSecret,
  secureCookies,
  sign,
  startSession,
  verify,
} from "./session";

const SECRET = "a-test-session-secret";
const NOW = new Date("2026-11-20T12:00:00Z");
const later = (seconds: number): Date => new Date(NOW.getTime() + seconds * 1000);

describe("a signed session", () => {
  it("is read back by the key that signed it", () => {
    const session = startSession("visitor", NOW);
    const read = verify(sign(session, SECRET), "visitor", SECRET, NOW);

    expect(read).toEqual(session);
    expect(session.id).toMatch(/^[0-9a-f]{32}$/);
    expect(session.expires).toBe(Math.floor(NOW.getTime() / 1000) + VISITOR_SECONDS);
  });

  it("gives every session its own id", () => {
    expect(newSessionId()).not.toBe(newSessionId());
  });

  it("is refused when any part of it is changed", () => {
    const session = startSession("visitor", NOW);
    const value = sign(session, SECRET);
    const [kind, id, expires, signature] = value.split(".");
    const otherId = id.startsWith("0") ? `1${id.slice(1)}` : `0${id.slice(1)}`;
    const tampered = [
      [kind, otherId, expires, signature],
      [kind, id, String(Number(expires) + 1), signature],
      ["a", id, expires, signature],
      [kind, id, expires, `${signature.slice(0, -1)}${signature.endsWith("A") ? "B" : "A"}`],
      [kind, id, expires, ""],
      [kind, id, expires],
    ];

    for (const parts of tampered) {
      expect(verify(parts.join("."), "visitor", SECRET, NOW)).toBeNull();
      expect(verify(parts.join("."), "admin", SECRET, NOW)).toBeNull();
    }
  });

  it("is refused under another key", () => {
    const value = sign(startSession("admin", NOW), SECRET);

    expect(verify(value, "admin", "another-secret", NOW)).toBeNull();
    expect(verify(value, "admin", "", NOW)).toBeNull();
  });

  it("is refused once it has expired", () => {
    const value = sign(startSession("admin", NOW), SECRET);

    expect(verify(value, "admin", SECRET, later(ADMIN_SECONDS - 1))).not.toBeNull();
    expect(verify(value, "admin", SECRET, later(ADMIN_SECONDS))).toBeNull();
    expect(verify(value, "admin", SECRET, later(ADMIN_SECONDS + 3600))).toBeNull();
  });

  it("of one kind is never read as the other", () => {
    const visitor = sign(startSession("visitor", NOW), SECRET);
    const admin = sign(startSession("admin", NOW), SECRET);

    expect(verify(visitor, "admin", SECRET, NOW)).toBeNull();
    expect(verify(admin, "visitor", SECRET, NOW)).toBeNull();
  });

  it("is refused when the cookie is missing or is not a session at all", () => {
    for (const value of [undefined, "", "admin", "a.b.c.d", "....", "v.zz.1.x"]) {
      expect(verify(value, "visitor", SECRET, NOW)).toBeNull();
    }
  });

  it("cannot be signed with no key", () => {
    expect(() => sign(startSession("visitor", NOW), "")).toThrow();
  });
});

describe("the cookie", () => {
  it("is HttpOnly, SameSite=Lax and on every path", () => {
    expect(cookieOptions(true, 60)).toEqual({
      httpOnly: true,
      sameSite: "lax",
      secure: true,
      path: "/",
      maxAge: 60,
    });
  });

  it("is Secure everywhere except a local address over plain http", () => {
    expect(secureCookies("domain-health.example", "https")).toBe(true);
    expect(secureCookies("domain-health.example", null)).toBe(true);
    expect(secureCookies("domain-health.example", "http")).toBe(true);
    expect(secureCookies(null, null)).toBe(true);
    expect(secureCookies("localhost:3000", "http")).toBe(false);
    expect(secureCookies("localhost:3000", null)).toBe(false);
    expect(secureCookies("127.0.0.1:3000", "http")).toBe(false);
    expect(secureCookies("localhost:3000", "https")).toBe(true);
    expect(secureCookies("localhost.example", "http")).toBe(true);
  });
});

describe("comparing the passphrase", () => {
  it("accepts the same text and nothing else", () => {
    expect(sameSecret("open sesame", "open sesame", SECRET)).toBe(true);
    expect(sameSecret("open sesamE", "open sesame", SECRET)).toBe(false);
    expect(sameSecret("", "open sesame", SECRET)).toBe(false);
    expect(sameSecret("open sesame and more", "open sesame", SECRET)).toBe(false);
  });
});
