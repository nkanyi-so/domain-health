import { describe, expect, it } from "vitest";
import { demoClientPage } from "@/data/demo-states";
import type { ClientPage } from "../api-types";
import { FALLBACK } from "../fallback";
import {
  advisoryChipFor,
  afterClick,
  clickAnnouncement,
  handledDates,
  handledItems,
  isHealthy,
  movedUpLine,
  ticksLine,
} from "./client-page";

const CLICK = new Date("2026-11-20T09:00:00Z");

function six(): ClientPage {
  const view = demoClientPage("handled-one");
  if (view.kind !== "snapshot") {
    throw new Error("not a snapshot");
  }
  // The same page before its one click.
  return afterClick(view.page, view.page.snapshot.ranked[0].id, "reopen", CLICK);
}

describe("marking a risk handled", () => {
  it("moves it out of the list and into the handled list, with its dates", () => {
    const page = FALLBACK.snapshots["oakhaven-outfitters"];
    const [first, second] = page.snapshot.ranked;
    const next = afterClick(page, first.id, "handled", CLICK);

    expect(next.snapshot.visible.map((risk) => risk.id)).toEqual([second.id]);
    expect(handledItems(next)).toEqual([
      { risk: first, dates: "Handled 20 Nov. Hidden until 20 Dec." },
    ]);
    expect(clickAnnouncement(next, first.id, "handled")).toBe(
      "Marked handled. Hidden until 20 Dec.",
    );
    expect(advisoryChipFor(next).text).toBe("1 advisory");
    // The page it was made from is not changed: a failed save puts it back.
    expect(page.snapshot.visible).toHaveLength(2);
    expect(page.handled).toEqual({});
  });

  it("brings the sixth risk into the list and says so", () => {
    const page = six();
    expect(page.snapshot.visible).toHaveLength(5);
    expect(movedUpLine(page)).toBeNull();

    const next = afterClick(page, page.snapshot.ranked[0].id, "handled", CLICK);

    expect(next.snapshot.visible).toHaveLength(5);
    expect(next.snapshot.visible.at(-1)?.id).toBe(page.snapshot.ranked[5].id);
    expect(movedUpLine(next)).toBe("1 handled. The next risk moved into the list.");
    expect(advisoryChipFor(next).text).toBe("5 advisory");
  });

  it("reopen puts the risk back in its place", () => {
    const page = six();
    const id = page.snapshot.ranked[2].id;
    const back = afterClick(afterClick(page, id, "handled", CLICK), id, "reopen", CLICK);

    expect(back.snapshot.visible.map((risk) => risk.id)).toEqual(
      page.snapshot.visible.map((risk) => risk.id),
    );
    expect(back.handled).toEqual({});
    expect(clickAnnouncement(back, id, "reopen")).toBe("Reopened.");
  });

  it("never touches the fixes", () => {
    const page = FALLBACK.snapshots["northwind-cycles"];
    const next = afterClick(page, page.snapshot.ranked[0].id, "handled", CLICK);

    expect(next.snapshot.fixes).toEqual(page.snapshot.fixes);
  });
});

describe("the page's words", () => {
  it("writes a mark's dates without the year", () => {
    expect(handledDates({ handled_at: "2026-11-20T09:00:00Z", until: "2026-12-20" })).toBe(
      "Handled 20 Nov. Hidden until 20 Dec.",
    );
  });

  it("says whose ticks these are", () => {
    expect(ticksLine(false)).toBe(
      "Only you see these ticks. They reset a day after your first one.",
    );
    expect(ticksLine(true)).toBe(
      "These ticks are on the shared list. Visitors do not see it: each has a list of their own.",
    );
  });

  it("calls a client healthy only when both lists are empty and nothing is handled", () => {
    const quiet = FALLBACK.snapshots["harbourlight-books"];
    const risky = FALLBACK.snapshots["willowmere-pets"];
    const allHandled = afterClick(risky, risky.snapshot.ranked[0].id, "handled", CLICK);

    expect(isHealthy(quiet)).toBe(true);
    expect(isHealthy(risky)).toBe(false);
    // No fix and no visible risk, but one was handled: not the healthy band.
    expect(allHandled.snapshot.visible).toHaveLength(0);
    expect(isHealthy(allHandled)).toBe(false);
  });
});
