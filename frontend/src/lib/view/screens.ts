// From what the backend answered to what a screen draws. Pure: the loaders in `lib/server/data.ts`
// fetch, this decides. A backend that cannot be reached gives the bundled snapshots; a backend
// that answers "no" (a 4xx) never does.

import type { ClientList, ClientPage } from "../api-types";
import type { FallbackData } from "../fallback";
import { type SnapshotState, snapshotState } from "./client-page";
import { type ClientRow, clientRows } from "./clients";

export type ListLoad = { kind: "ok"; list: ClientList } | { kind: "unreachable" };

export type ClientListView =
  | { kind: "loading" }
  | {
      kind: "list";
      rows: ClientRow[];
      /** The day the bundled snapshots were saved for, when they are what is shown. */
      fallbackDay: string | null;
    };

export function clientListView(load: ListLoad, fallback: FallbackData): ClientListView {
  if (load.kind === "unreachable") {
    return {
      kind: "list",
      rows: clientRows(fallback.clients, false),
      fallbackDay: fallback.generated_for_day,
    };
  }
  return { kind: "list", rows: clientRows(load.list, true), fallbackDay: null };
}

export type PageLoad =
  | { kind: "ok"; page: ClientPage }
  | { kind: "no-snapshot" }
  | { kind: "no-such-client" }
  | { kind: "unreachable" };

export interface KnownClient {
  id: string;
  name: string;
  domain: string;
}

/**
 * Whether "Mark handled" and "Reopen" work on this view.
 * `on`: they save. `local`: a demo state, they change this page only. `old-day`: an earlier
 * snapshot is shown in place of today's. `fallback`: the backend cannot be reached.
 */
export type Writes = "on" | "local" | "old-day" | "fallback";

export type ClientPageView =
  | { kind: "loading" }
  | { kind: "no-such-client" }
  /** Today has no snapshot and there is no earlier one to show. */
  | { kind: "no-snapshot"; client: KnownClient }
  | {
      kind: "snapshot";
      page: ClientPage;
      state: SnapshotState;
      /** Set when today has no snapshot and this earlier one is shown in its place. */
      shownInsteadOfToday: boolean;
      fallbackDay: string | null;
      admin: boolean;
      writes: Writes;
      /**
       * How many of the ranked risks were recorded for other seeded clients and moved onto this
       * page. Only a demo state ever has any.
       */
      borrowedRisks: number;
    };

export interface ClientPageLoads {
  id: string;
  today: PageLoad;
  /** Asked for only when today has no snapshot: the day before. */
  earlier: PageLoad | null;
  admin: boolean;
}

function known(id: string, fallback: FallbackData): KnownClient {
  const client = fallback.clients.clients.find((entry) => entry.id === id);
  return client ? { id, name: client.name, domain: client.domain } : { id, name: id, domain: "" };
}

export function snapshotView(
  page: ClientPage,
  rest: {
    shownInsteadOfToday?: boolean;
    fallbackDay?: string | null;
    admin?: boolean;
    writes: Writes;
    borrowedRisks?: number;
  },
): ClientPageView {
  return {
    kind: "snapshot",
    page,
    state: snapshotState(page),
    shownInsteadOfToday: rest.shownInsteadOfToday ?? false,
    fallbackDay: rest.fallbackDay ?? null,
    admin: rest.admin ?? false,
    writes: rest.writes,
    borrowedRisks: rest.borrowedRisks ?? 0,
  };
}

const COUNT_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight"];

function countWord(count: number): string {
  return COUNT_WORDS[count] ?? String(count);
}

/**
 * The "Model output" fact on a client page. A page that carries risks recorded for another
 * client says so here, and never says its list is one recorded model run.
 */
export function modelOutputFact(view: { page: ClientPage; borrowedRisks: number }): string {
  const { snapshot } = view.page;
  if (snapshot.risks_status === "unavailable") {
    return "Dropped: it did not pass its checks";
  }
  if (view.borrowedRisks > 0) {
    return `Put together for this demo state: ${countWord(view.borrowedRisks)} of these risks were recorded for other seeded clients and moved here to show ${countWord(snapshot.ranked.length)}. Their wording does not describe this client.`;
  }
  return "Recorded from a real model run, not generated on this visit";
}

export function clientPageView(loads: ClientPageLoads, fallback: FallbackData): ClientPageView {
  const { id, today, earlier, admin } = loads;
  switch (today.kind) {
    case "ok":
      return snapshotView(today.page, { admin, writes: "on" });
    case "no-such-client":
      return { kind: "no-such-client" };
    case "unreachable": {
      const saved = Object.hasOwn(fallback.snapshots, id) ? fallback.snapshots[id] : null;
      // The bundled pages were made as the shared list with nothing handled: no one is signed in
      // to anything while they show, and nothing can be marked.
      return saved
        ? snapshotView(saved, { fallbackDay: fallback.generated_for_day, writes: "fallback" })
        : { kind: "no-such-client" };
    }
    case "no-snapshot":
      return earlier?.kind === "ok"
        ? snapshotView(earlier.page, { shownInsteadOfToday: true, admin, writes: "old-day" })
        : { kind: "no-snapshot", client: known(id, fallback) };
  }
}

/** The fallback notice's words (state 15). */
export function fallbackNotice(day: string, formatDay: (day: string) => string): string {
  return `The live service cannot be reached. These are the snapshots saved with this page on ${formatDay(day)}. Marking handled and the live check are switched off until it is back.`;
}
