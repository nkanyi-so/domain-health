import { describe, expect, it } from "vitest";
import { DEMO_RESULT } from "@/data/demo-states";
import {
  NO_LOOKUP,
  REFUSAL_TITLE,
  ageLine,
  finishedAnnouncement,
  liveCheckView,
  lookingUp,
  refusalMessage,
  shouldStart,
} from "./live-check";

const NOW = new Date("2026-11-20T14:06:30Z");

describe("the words for a refusal", () => {
  it("has one line for each reason the backend names", () => {
    expect(refusalMessage("ip_address")).toBe(
      "That is an IP address. Type a domain name, like example.com.",
    );
    expect(refusalMessage("single_label")).toBe(
      "A domain name has at least two parts, like example.com.",
    );
    expect(refusalMessage("too_long")).toBe(
      "That is longer than a domain name can be (253 characters).",
    );
    expect(refusalMessage("reserved")).toBe(
      "That name is reserved, so no one can send mail from it.",
    );
    expect(refusalMessage("internal")).toBe("That is an internal name, not a public domain.");
    expect(refusalMessage("scheme")).toBe(
      "That is a web address. Leave out everything but the domain, like example.com.",
    );
    expect(refusalMessage("path")).toBe(refusalMessage("scheme"));
    expect(refusalMessage("port")).toBe(
      "Leave out the port. Type the domain only, like example.com.",
    );
    expect(refusalMessage("not_a_name")).toBe(
      "That is not a domain name. Type one like example.com.",
    );
  });

  it("falls to the last line for a reason it does not know", () => {
    for (const reason of ["", "something_new", "constructor", "toString"]) {
      expect(refusalMessage(reason)).toBe("That is not a domain name. Type one like example.com.");
    }
  });

  it("keeps the banner's first and last lines", () => {
    expect(REFUSAL_TITLE).toBe("That is not a domain this can check");
    expect(NO_LOOKUP).toBe("No lookup was made.");
  });
});

describe("what an answer from the live-check route shows", () => {
  it("a 200 is the result", () => {
    expect(liveCheckView(200, DEMO_RESULT, "example.com", NOW)).toEqual({
      kind: "result",
      result: DEMO_RESULT,
      ageLine: null,
    });
  });

  it("a 422 is a refusal with its reason's words, keeping what was typed", () => {
    expect(liveCheckView(422, { refused: "ip_address" }, "192.0.2.1", NOW)).toEqual({
      kind: "refused",
      domain: "192.0.2.1",
      message: refusalMessage("ip_address"),
    });
    expect(liveCheckView(422, null, "???", NOW)).toMatchObject({
      kind: "refused",
      message: refusalMessage("not_a_name"),
    });
  });

  it("a 429 is the address limit or the day's cap", () => {
    expect(liveCheckView(429, { refused: "rate_limited" }, "example.com", NOW)).toEqual({
      kind: "rate-limited",
    });
    expect(liveCheckView(429, { refused: "daily_cap" }, "example.com", NOW)).toEqual({
      kind: "cap-reached",
    });
  });

  it("a 503 switches the check off; anything else is a failure", () => {
    expect(liveCheckView(503, { error: "unreachable" }, "example.com", NOW)).toEqual({
      kind: "switched-off",
    });
    for (const status of [400, 403, 500, 502]) {
      expect(liveCheckView(status, null, "example.com", NOW)).toEqual({ kind: "failed" });
    }
    expect(liveCheckView(200, { not: "a result" }, "example.com", NOW)).toEqual({ kind: "failed" });
  });
});

describe("a result's words", () => {
  it("says how old a kept result is", () => {
    const kept = { ...DEMO_RESULT, cached: true };

    expect(ageLine(kept, NOW)).toBe(
      "This result is 4 minutes old. Results are kept for ten minutes.",
    );
    expect(ageLine(kept, new Date("2026-11-20T14:03:10Z"))).toBe(
      "This result is 1 minute old. Results are kept for ten minutes.",
    );
    expect(ageLine(kept, new Date("2026-11-20T14:02:20Z"))).toBe(
      "This result is less than a minute old. Results are kept for ten minutes.",
    );
    expect(ageLine(DEMO_RESULT, NOW)).toBeNull();
  });

  it("is announced when it starts and when it finishes", () => {
    expect(lookingUp("example.com")).toBe("Looking up DNS records for example.com.");
    expect(finishedAnnouncement(DEMO_RESULT)).toBe("Check finished: 1 fix.");
    expect(finishedAnnouncement({ ...DEMO_RESULT, fixes: [] })).toBe(
      "Check finished: nothing to fix.",
    );
    expect(
      finishedAnnouncement({ ...DEMO_RESULT, fixes: [...DEMO_RESULT.fixes, ...DEMO_RESULT.fixes] }),
    ).toBe("Check finished: 2 fixes.");
  });
});

describe("starting a check as the page opens", () => {
  it("starts only for the domain the visitor's own press left a marker for", () => {
    expect(shouldStart("example.com", "example.com")).toBe(true);
  });

  it("does not start from an address alone, as a shared link or a crawler arrives", () => {
    expect(shouldStart(null, "example.com")).toBe(false);
  });

  it("does not start for another domain, or for none", () => {
    expect(shouldStart("example.org", "example.com")).toBe(false);
    expect(shouldStart("", "")).toBe(false);
    expect(shouldStart("example.com", "")).toBe(false);
  });
});
