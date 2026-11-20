import { describe, expect, it } from "vitest";
import { LOCAL_ADDRESS, clientAddress, sameOrigin } from "./request";

function bag(values: Record<string, string>): { get(name: string): string | null } {
  return { get: (name) => values[name.toLowerCase()] ?? null };
}

describe("the origin check on writes", () => {
  it("accepts a request from this site's own pages", () => {
    expect(sameOrigin("https://domain-health.example", "domain-health.example")).toBe(true);
    expect(sameOrigin("http://localhost:3000", "localhost:3000")).toBe(true);
    expect(sameOrigin("https://Domain-Health.example", "domain-health.example")).toBe(true);
  });

  it("refuses another site, another port and a look-alike host", () => {
    expect(sameOrigin("https://elsewhere.example", "domain-health.example")).toBe(false);
    expect(sameOrigin("http://localhost:4000", "localhost:3000")).toBe(false);
    expect(
      sameOrigin("https://domain-health.example.elsewhere.example", "domain-health.example"),
    ).toBe(false);
    expect(
      sameOrigin("https://elsewhere.example/domain-health.example", "domain-health.example"),
    ).toBe(false);
  });

  it("refuses a write with no Origin, or one that is not an address", () => {
    expect(sameOrigin(null, "domain-health.example")).toBe(false);
    expect(sameOrigin("", "domain-health.example")).toBe(false);
    expect(sameOrigin("null", "domain-health.example")).toBe(false);
    expect(sameOrigin("domain-health.example", "domain-health.example")).toBe(false);
    expect(sameOrigin("file:///etc/hosts", "")).toBe(false);
    expect(sameOrigin("https://domain-health.example", null)).toBe(false);
  });
});

describe("the visitor's address", () => {
  it("is the first entry of x-forwarded-for, never the list", () => {
    expect(clientAddress(bag({ "x-forwarded-for": "203.0.113.7, 198.51.100.2, 10.0.0.1" }))).toBe(
      "203.0.113.7",
    );
    expect(clientAddress(bag({ "x-forwarded-for": " 2001:db8::1 ,203.0.113.7" }))).toBe(
      "2001:db8::1",
    );
  });

  it("falls to x-real-ip, then to the local address", () => {
    expect(clientAddress(bag({ "x-real-ip": "203.0.113.9" }))).toBe("203.0.113.9");
    expect(clientAddress(bag({}))).toBe(LOCAL_ADDRESS);
    expect(LOCAL_ADDRESS).toBe("127.0.0.1");
  });

  it("never passes on text that is not one IP address", () => {
    const strange = ["unknown", "203.0.113.7:4321", "fe80::1%eth0", "203.0.113.7 198.51.100.2", ""];
    for (const first of strange) {
      expect(clientAddress(bag({ "x-forwarded-for": first, "x-real-ip": "203.0.113.9" }))).toBe(
        "203.0.113.9",
      );
      expect(clientAddress(bag({ "x-forwarded-for": first }))).toBe(LOCAL_ADDRESS);
    }
  });
});
