// A client's page: which of the states it is in, what the handled list holds, and what a click
// on "Mark handled" or "Reopen" does to the view before the server answers.

import type { ClientPage, HandledMark, Risk } from "../api-types";
import { type AdvisoryChip, advisoryChip } from "./clients";
import { addDays, formatDayShort, utcDay } from "./format";

/** The states a snapshot can show (docs/DESIGN.md, states 2 to 8). */
export type SnapshotState =
  | "healthy"
  | "fixes-only"
  | "risks-only"
  | "both"
  | "handled-one"
  | "all-handled"
  | "risks-unavailable";

export const VISIBLE_CAP = 5;
export const HANDLED_DAYS = 30;

export function snapshotState(page: ClientPage): SnapshotState {
  const { snapshot } = page;
  if (snapshot.risks_status === "unavailable") {
    return "risks-unavailable";
  }
  if (snapshot.suppressed.length > 0) {
    return snapshot.visible.length === 0 ? "all-handled" : "handled-one";
  }
  const fixes = snapshot.fixes.length > 0;
  const risks = snapshot.visible.length > 0;
  if (fixes && risks) {
    return "both";
  }
  if (fixes) {
    return "fixes-only";
  }
  return risks ? "risks-only" : "healthy";
}

/** The healthy band needs both lists empty, with nothing handled either. */
export function isHealthy(page: ClientPage): boolean {
  return snapshotState(page) === "healthy";
}

export function advisoryChipFor(page: ClientPage): AdvisoryChip {
  return advisoryChip(page.snapshot.risks_status, page.snapshot.visible.length);
}

export interface HandledItem {
  risk: Risk;
  /** "Handled 20 Nov. Hidden until 20 Dec." */
  dates: string;
}

export function handledDates(mark: HandledMark): string {
  return `Handled ${formatDayShort(mark.handled_at)}. Hidden until ${formatDayShort(mark.until)}.`;
}

/** The handled risks, in the snapshot's order, each with its dates. */
export function handledItems(page: ClientPage): HandledItem[] {
  return page.snapshot.suppressed.map((risk) => {
    const mark = page.handled[risk.id];
    return { risk, dates: mark ? handledDates(mark) : "Handled." };
  });
}

/**
 * The line under the list when a risk beyond the first five has moved into view: "1 handled.
 * The next risk moved into the list." Null when nothing moved up.
 */
export function movedUpLine(page: ClientPage): string | null {
  const { ranked, visible, suppressed } = page.snapshot;
  const waiting = new Set(ranked.slice(VISIBLE_CAP).map((risk) => risk.id));
  const moved = visible.filter((risk) => waiting.has(risk.id)).length;
  if (moved === 0) {
    return null;
  }
  const next = moved === 1 ? "The next risk" : `The next ${moved} risks`;
  return `${suppressed.length} handled. ${next} moved into the list.`;
}

export type ClickAction = "handled" | "reopen";

/**
 * The page as it will read after a click, worked out here so the list changes at once. The
 * server's answer replaces it; if the save fails the page before the click is put back.
 * Follows the store's rule: the first five ranked risks that carry no mark still in force.
 */
export function afterClick(
  page: ClientPage,
  riskId: string,
  action: ClickAction,
  now: Date,
): ClientPage {
  const today = utcDay(now);
  const handled: Record<string, HandledMark> = { ...page.handled };
  if (action === "handled") {
    handled[riskId] = { handled_at: now.toISOString(), until: addDays(today, HANDLED_DAYS) };
  } else {
    delete handled[riskId];
  }
  const hidden = (risk: Risk): boolean => {
    const mark = handled[risk.id];
    return mark !== undefined && today < mark.until;
  };
  const { ranked } = page.snapshot;
  return {
    ...page,
    handled,
    snapshot: {
      ...page.snapshot,
      visible: ranked.filter((risk) => !hidden(risk)).slice(0, VISIBLE_CAP),
      suppressed: ranked.filter(hidden),
    },
  };
}

/** What the live region says after a click. */
export function clickAnnouncement(page: ClientPage, riskId: string, action: ClickAction): string {
  if (action === "reopen") {
    return "Reopened.";
  }
  const mark = page.handled[riskId];
  return mark ? `Marked handled. Hidden until ${formatDayShort(mark.until)}.` : "Marked handled.";
}

/** Whose ticks these are, under the "Handled" heading. */
export function ticksLine(admin: boolean): string {
  return admin
    ? "These ticks are on the shared list. Visitors do not see it: each has a list of their own."
    : "Only you see these ticks. They reset a day after your first one.";
}
