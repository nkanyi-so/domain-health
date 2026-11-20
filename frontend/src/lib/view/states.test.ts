// The seventeen states in docs/DESIGN.md, each reached from what the backend answers (or, where
// the design says so, from its `?demo=` flag), and each mapped to the view its screen draws.

import { describe, expect, it } from "vitest";
import { DEMO_DAY, demoClientList, demoClientPage, demoLiveCheck } from "@/data/demo-states";
import type { ClientPage } from "../api-types";
import { FALLBACK } from "../fallback";
import { afterClick, movedUpLine, snapshotState } from "./client-page";
import { DEMO_STATES, demoName, demoNotice } from "./demo";
import { liveCheckView } from "./live-check";
import { type ClientPageView, clientListView, clientPageView } from "./screens";

const NOW = new Date("2026-01-04T12:00:00Z");

function saved(id: string): ClientPage {
  return FALLBACK.snapshots[id];
}

function answered(page: ClientPage, admin = false): ClientPageView {
  return clientPageView(
    { id: page.id, today: { kind: "ok", page }, earlier: null, admin },
    FALLBACK,
  );
}

function stateOf(view: ClientPageView): string {
  return view.kind === "snapshot" ? view.state : view.kind;
}

describe("the seventeen states", () => {
  it("1: loading", () => {
    expect(demoClientList("loading")).toEqual({ kind: "loading" });
  });

  it("2: healthy, nothing to do (Harbourlight Books)", () => {
    const view = answered(saved("harbourlight-books"));

    expect(stateOf(view)).toBe("healthy");
    expect(stateOf(demoClientPage("healthy"))).toBe("healthy");
  });

  it("3: fixes only (Fernhollow Garden Supply)", () => {
    expect(stateOf(answered(saved("fernhollow-garden")))).toBe("fixes-only");
    expect(stateOf(answered(saved("inkwell-and-vine")))).toBe("fixes-only");
    expect(stateOf(demoClientPage("fixes-only"))).toBe("fixes-only");
  });

  it("4: risks only (Oakhaven Outfitters)", () => {
    expect(stateOf(answered(saved("oakhaven-outfitters")))).toBe("risks-only");
    expect(stateOf(demoClientPage("risks-only"))).toBe("risks-only");
  });

  it("5: both (Northwind Cycles)", () => {
    expect(stateOf(answered(saved("northwind-cycles")))).toBe("both");
    expect(stateOf(demoClientPage("both"))).toBe("both");
  });

  it("6: a handled risk, the next one moved up (six ranked risks, through the flag)", () => {
    const view = demoClientPage("handled-one");
    if (view.kind !== "snapshot") {
      throw new Error("not a snapshot");
    }
    const { snapshot } = view.page;

    expect(view.state).toBe("handled-one");
    expect(snapshot.ranked).toHaveLength(6);
    expect(snapshot.suppressed.map((risk) => risk.id)).toEqual([snapshot.ranked[0].id]);
    expect(snapshot.visible.map((risk) => risk.id)).toEqual(
      snapshot.ranked.slice(1).map((risk) => risk.id),
    );
    expect(movedUpLine(view.page)).toBe("1 handled. The next risk moved into the list.");
    expect(new Set(snapshot.ranked.map((risk) => risk.id)).size).toBe(6);
    for (const risk of snapshot.ranked) {
      expect(risk.id).toBe(`${risk.type}:${snapshot.domain}`);
    }
  });

  it("6, from the backend: a click on a seeded client hides the risk", () => {
    const page = saved("oakhaven-outfitters");
    const clicked = afterClick(page, page.snapshot.ranked[0].id, "handled", NOW);

    expect(stateOf(answered(clicked))).toBe("handled-one");
    expect(movedUpLine(clicked)).toBeNull();
  });

  it("7: everything handled", () => {
    const page = saved("oakhaven-outfitters");
    const all = page.snapshot.ranked.reduce(
      (seen, risk) => afterClick(seen, risk.id, "handled", NOW),
      page,
    );

    expect(stateOf(answered(all))).toBe("all-handled");
    expect(stateOf(demoClientPage("all-handled"))).toBe("all-handled");
  });

  it("8: risks unavailable", () => {
    const page = saved("northwind-cycles");
    const dropped: ClientPage = {
      ...page,
      snapshot: { ...page.snapshot, risks_status: "unavailable", ranked: [], visible: [] },
    };

    expect(stateOf(answered(dropped))).toBe("risks-unavailable");
    expect(stateOf(demoClientPage("risks-unavailable"))).toBe("risks-unavailable");
    expect(clientListView({ kind: "ok", list: FALLBACK.clients }, FALLBACK).kind).toBe("list");
  });

  it("9: no snapshot today, with the day before shown or with nothing to show", () => {
    const id = "driftwood-coffee";
    const earlier = saved(id);
    const latest = clientPageView(
      { id, today: { kind: "no-snapshot" }, earlier: { kind: "ok", page: earlier }, admin: false },
      FALLBACK,
    );
    const alone = clientPageView(
      { id, today: { kind: "no-snapshot" }, earlier: { kind: "no-snapshot" }, admin: false },
      FALLBACK,
    );
    const demo = demoClientPage("no-snapshot");

    expect(latest).toMatchObject({
      kind: "snapshot",
      shownInsteadOfToday: true,
      writes: "old-day",
    });
    expect(alone).toMatchObject({
      kind: "no-snapshot",
      client: { name: "Driftwood Coffee Roasters" },
    });
    expect(demo).toMatchObject({ kind: "snapshot", shownInsteadOfToday: true, writes: "old-day" });
    expect(demo.kind === "snapshot" && demo.page.snapshot.day).toBe("2026-11-19");
  });

  it("10: live check running", () => {
    expect(demoLiveCheck("running", "example.com")).toEqual({
      kind: "running",
      domain: "example.com",
    });
  });

  it("11: live check result", () => {
    const demo = demoLiveCheck("result", "example.com");

    expect(demo.kind).toBe("result");
    expect(demo.kind === "result" && liveCheckView(200, demo.result, "example.com", NOW)).toEqual(
      demo,
    );
  });

  it("12: live check refused", () => {
    expect(liveCheckView(422, { refused: "ip_address" }, "192.0.2.1", NOW)).toEqual(
      demoLiveCheck("refused", "192.0.2.1"),
    );
  });

  it("13: rate limited", () => {
    expect(liveCheckView(429, { refused: "rate_limited" }, "example.com", NOW)).toEqual(
      demoLiveCheck("rate-limited", "example.com"),
    );
  });

  it("14: daily cap reached", () => {
    expect(liveCheckView(429, { refused: "daily_cap" }, "example.com", NOW)).toEqual(
      demoLiveCheck("cap-reached", "example.com"),
    );
  });

  it("15: backend unreachable (fallback)", () => {
    const list = clientListView({ kind: "unreachable" }, FALLBACK);
    const page = clientPageView(
      { id: "oakhaven-outfitters", today: { kind: "unreachable" }, earlier: null, admin: false },
      FALLBACK,
    );

    expect(list).toEqual(demoClientList("fallback"));
    expect(list).toMatchObject({ kind: "list", fallbackDay: "2026-01-04" });
    expect(list.kind === "list" && list.rows).toHaveLength(12);
    expect(page).toMatchObject({ kind: "snapshot", fallbackDay: "2026-01-04", writes: "fallback" });
  });

  it("16: admin signed in (no flag: reached by signing in)", () => {
    const shared: ClientPage = { ...saved("oakhaven-outfitters"), scope: "shared" };

    expect(answered(shared, true)).toMatchObject({ kind: "snapshot", admin: true, writes: "on" });
    expect(answered(shared, false)).toMatchObject({ kind: "snapshot", admin: false, writes: "on" });
    expect(Object.values(DEMO_STATES).flat()).not.toContain("admin");
  });

  it("17: sign-in refused", () => {
    expect(demoName("admin", "refused")).toBe("refused");
    expect(demoName("admin", "signed-in")).toBeNull();
  });
});

describe("the demo flag", () => {
  it("has a name for every state the design lists a flag for", () => {
    expect(DEMO_STATES).toEqual({
      list: ["loading", "fallback"],
      client: [
        "healthy",
        "fixes-only",
        "risks-only",
        "both",
        "handled-one",
        "all-handled",
        "risks-unavailable",
        "no-snapshot",
      ],
      check: ["running", "result", "refused", "rate-limited", "cap-reached"],
      admin: ["refused"],
    });
  });

  it("ignores a name its screen does not have", () => {
    expect(demoName("list", "healthy")).toBeNull();
    expect(demoName("client", "loading")).toBeNull();
    expect(demoName("check", undefined)).toBeNull();
    expect(demoName("check", ["result", "refused"])).toBe("result");
    expect(demoName("list", "__proto__")).toBeNull();
  });

  it("names itself in the footer", () => {
    expect(demoNotice("handled-one")).toBe("Showing a demo state: handled-one.");
  });

  it("draws every client state as a visitor's own page on the demo day, never as admin", () => {
    for (const name of DEMO_STATES.client) {
      const view = demoClientPage(name);
      if (view.kind !== "snapshot") {
        throw new Error(`${name} is not a snapshot`);
      }
      expect(view.admin).toBe(false);
      expect(view.writes).not.toBe("on");
      expect(view.fallbackDay).toBeNull();
      expect(view.page.scope).toBe("sandbox");
      expect(view.state).toBe(snapshotState(view.page));
      expect(view.page.snapshot.day).toBe(name === "no-snapshot" ? "2026-11-19" : DEMO_DAY);
      expect(view.page.snapshot.domain.endsWith(".example")).toBe(true);
    }
  });
});
