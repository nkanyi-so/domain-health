import { describe, expect, it } from "vitest";
import { FALLBACK } from "../fallback";
import { clientListView, clientPageView } from "../view/screens";
import { type Fetch, callBackend, detailOf } from "./backend";

const CONFIG = { url: "https://service.example", proxySecret: "a-proxy-secret" };
const GET = { method: "GET" as const, path: "/api/clients", actor: "admin", timeoutMs: 1000 };

function answering(status: number, body: unknown): Fetch {
  return async () =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), { status });
}

describe("a call to the backend", () => {
  it("carries the proxy secret, the actor and, when given, the one client address", async () => {
    const seen: { url: string; init: RequestInit }[] = [];
    const fetchImpl: Fetch = async (url, init) => {
      seen.push({ url, init });
      return new Response("{}", { status: 200 });
    };

    await callBackend(CONFIG, GET, fetchImpl);
    await callBackend(
      CONFIG,
      {
        method: "POST",
        path: "/api/live-check",
        actor: "sandbox:" + "ab".repeat(16),
        body: { domain: "example.com" },
        clientAddress: "203.0.113.7",
        timeoutMs: 1000,
      },
      fetchImpl,
    );

    const first = seen[0].init.headers as Record<string, string>;
    expect(seen[0].url).toBe("https://service.example/api/clients");
    expect(first["X-Proxy-Secret"]).toBe("a-proxy-secret");
    expect(first["X-Actor"]).toBe("admin");
    expect(first["X-Client-Address"]).toBeUndefined();
    expect(seen[0].init.signal).toBeInstanceOf(AbortSignal);

    const second = seen[1].init.headers as Record<string, string>;
    expect(second["X-Actor"]).toBe("sandbox:" + "ab".repeat(16));
    expect(second["X-Client-Address"]).toBe("203.0.113.7");
    expect(seen[1].init.body).toBe('{"domain":"example.com"}');
  });

  it("is ok on a 2xx with a JSON body", async () => {
    expect(await callBackend(CONFIG, GET, answering(200, { clients: [] }))).toEqual({
      kind: "ok",
      status: 200,
      body: { clients: [] },
    });
  });

  it("is unreachable on a network error, a timeout and any 5xx", async () => {
    const down: Fetch = async () => {
      throw new TypeError("fetch failed");
    };
    const slow: Fetch = async () => {
      throw new DOMException("timed out", "TimeoutError");
    };

    expect(await callBackend(CONFIG, GET, down)).toEqual({ kind: "unreachable", why: "network" });
    expect(await callBackend(CONFIG, GET, slow)).toEqual({ kind: "unreachable", why: "timeout" });
    for (const status of [500, 502, 503, 504]) {
      expect((await callBackend(CONFIG, GET, answering(status, "down"))).kind).toBe("unreachable");
    }
    expect((await callBackend(CONFIG, GET, answering(200, "<html>a login page</html>"))).kind).toBe(
      "unreachable",
    );
  });

  it("gives up on its own when the backend does not answer in time", async () => {
    const never: Fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      });

    expect(await callBackend(CONFIG, { ...GET, timeoutMs: 20 }, never)).toEqual({
      kind: "unreachable",
      why: "timeout",
    });
  });

  it("is refused, not unreachable, on a 4xx: the backend answered", async () => {
    for (const status of [400, 401, 404, 422, 429]) {
      const answer = await callBackend(CONFIG, GET, answering(status, { detail: "no" }));
      expect(answer).toEqual({ kind: "refused", status, body: { detail: "no" } });
    }
    expect(detailOf({ detail: { refused: "rate_limited" } })).toEqual({ refused: "rate_limited" });
    expect(detailOf("text")).toBeNull();
  });
});

describe("the fallback switch", () => {
  it("serves the bundled snapshots only when the backend is unreachable", () => {
    const away = clientListView({ kind: "unreachable" }, FALLBACK);
    expect(away).toMatchObject({ kind: "list", fallbackDay: FALLBACK.generated_for_day });

    const live = clientListView({ kind: "ok", list: FALLBACK.clients }, FALLBACK);
    expect(live).toMatchObject({ kind: "list", fallbackDay: null });
  });

  it("never serves them for a 4xx: no snapshot and no such client stay what they are", () => {
    const id = "northwind-cycles";
    const none = clientPageView(
      { id, today: { kind: "no-snapshot" }, earlier: { kind: "no-snapshot" }, admin: false },
      FALLBACK,
    );
    const unknown = clientPageView(
      { id: "no-one", today: { kind: "no-such-client" }, earlier: null, admin: false },
      FALLBACK,
    );
    const away = clientPageView(
      { id, today: { kind: "unreachable" }, earlier: null, admin: true },
      FALLBACK,
    );

    expect(none).toEqual({
      kind: "no-snapshot",
      client: { id, name: "Northwind Cycles", domain: "northwind-cycles.example" },
    });
    expect(unknown).toEqual({ kind: "no-such-client" });
    // Away: the saved page, with writes off and no one treated as admin.
    expect(away).toMatchObject({
      kind: "snapshot",
      fallbackDay: FALLBACK.generated_for_day,
      writes: "fallback",
      admin: false,
    });
  });
});
