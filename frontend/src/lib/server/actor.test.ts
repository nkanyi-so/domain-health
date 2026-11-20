import { describe, expect, it } from "vitest";
import { NO_SESSION, chooseActor } from "./actor";
import { ADMIN_COOKIE, VISITOR_COOKIE, sign, startSession } from "./session";

const SECRET = "a-test-session-secret";
const NOW = new Date("2026-11-20T12:00:00Z");

describe("who a request acts as", () => {
  it("is the visitor's own sandbox when their cookie is valid", () => {
    const session = startSession("visitor", NOW);
    const actor = chooseActor({ [VISITOR_COOKIE]: sign(session, SECRET) }, SECRET, NOW);

    expect(actor).toEqual({ header: `sandbox:${session.id}`, admin: false, session: session.id });
    expect(actor.header).toMatch(/^sandbox:[0-9a-f]{32}$/);
  });

  it("is the admin when the admin cookie is valid, whatever else is sent", () => {
    const visitor = startSession("visitor", NOW);
    const cookies = {
      [VISITOR_COOKIE]: sign(visitor, SECRET),
      [ADMIN_COOKIE]: sign(startSession("admin", NOW), SECRET),
    };

    expect(chooseActor(cookies, SECRET, NOW)).toEqual({
      header: "admin",
      admin: true,
      session: visitor.id,
    });
  });

  it("is the empty sandbox with no cookie: reading needs no session", () => {
    expect(chooseActor({}, SECRET, NOW)).toEqual({
      header: `sandbox:${NO_SESSION}`,
      admin: false,
      session: null,
    });
    expect(NO_SESSION).toMatch(/^[0-9a-f]{32}$/);
  });

  it("is never the admin on a forged, expired or wrong-kind admin cookie", () => {
    const expired = new Date(NOW.getTime() + 13 * 60 * 60 * 1000);
    const real = sign(startSession("admin", NOW), SECRET);
    const forged = [
      "admin",
      sign(startSession("admin", NOW), "another-secret"),
      sign(startSession("visitor", NOW), SECRET),
      `${real}x`,
    ];

    for (const value of forged) {
      expect(chooseActor({ [ADMIN_COOKIE]: value }, SECRET, NOW).admin).toBe(false);
    }
    expect(chooseActor({ [ADMIN_COOKIE]: real }, SECRET, expired).admin).toBe(false);
    expect(chooseActor({ [ADMIN_COOKIE]: real }, SECRET, NOW).admin).toBe(true);
  });

  it("trusts no cookie at all when there is no session secret", () => {
    const cookies = {
      [VISITOR_COOKIE]: sign(startSession("visitor", NOW), SECRET),
      [ADMIN_COOKIE]: sign(startSession("admin", NOW), SECRET),
    };

    expect(chooseActor(cookies, null, NOW)).toEqual({
      header: `sandbox:${NO_SESSION}`,
      admin: false,
      session: null,
    });
  });
});
