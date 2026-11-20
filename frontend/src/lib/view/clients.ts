// The client list: what each row says and the order of the rows.

import type { ClientList, ClientSummary } from "../api-types";
import { formatDay, plural } from "./format";

export type AdvisoryChip =
  | { kind: "count"; text: string }
  | { kind: "none"; text: "No advisory" }
  | { kind: "unavailable"; text: "Risks unavailable" };

export interface ClientRow {
  id: string;
  name: string;
  domain: string;
  /** Null when the day has no snapshot: the row then shows no chips. */
  fixes: { count: number; text: string } | null;
  advisory: AdvisoryChip | null;
  snapshot: string;
}

export function fixesText(count: number): string {
  return count === 0 ? "Nothing to fix" : plural(count, "fix", "fixes");
}

export function advisoryChip(status: "ranked" | "unavailable", visible: number): AdvisoryChip {
  if (status === "unavailable") {
    return { kind: "unavailable", text: "Risks unavailable" };
  }
  return visible === 0
    ? { kind: "none", text: "No advisory" }
    : { kind: "count", text: `${visible} advisory` };
}

/**
 * Most fixes first, then by name. The advisory count never sorts anything: a client with five
 * risks and no fix comes after a client with one fix.
 */
export function sortClients(clients: readonly ClientSummary[]): ClientSummary[] {
  return [...clients].sort(
    (a, b) => (b.today?.fixes ?? 0) - (a.today?.fixes ?? 0) || a.name.localeCompare(b.name, "en"),
  );
}

/** `today` is the day the list is for; a snapshot of another day shows its date. */
export function clientRows(list: ClientList, isToday: boolean): ClientRow[] {
  return sortClients(list.clients).map((client) => {
    const day = client.today;
    return {
      id: client.id,
      name: client.name,
      domain: client.domain,
      fixes: day ? { count: day.fixes, text: fixesText(day.fixes) } : null,
      advisory: day ? advisoryChip(day.risks_status, day.risks_visible) : null,
      snapshot: !day ? "No snapshot today" : isToday ? "Today" : formatDay(day.day),
    };
  });
}
