import { describe, expect, it } from "vitest";
import type { ClientList, ClientSummary } from "../api-types";
import { FALLBACK } from "../fallback";
import { advisoryChip, clientRows, fixesText, sortClients } from "./clients";

function client(
  name: string,
  fixes: number | null,
  risks = 0,
  status: "ranked" | "unavailable" = "ranked",
): ClientSummary {
  return {
    id: name.toLowerCase().replace(/[^a-z]+/g, "-"),
    name,
    domain: `${name.toLowerCase().replace(/[^a-z]+/g, "-")}.example`,
    seeded: true,
    today:
      fixes === null
        ? null
        : {
            day: "2026-11-20",
            fixes,
            risks_visible: risks,
            risks_handled: 0,
            risks_status: status,
          },
  };
}

const names = (clients: ClientSummary[]): string[] => clients.map((entry) => entry.name);

describe("the order of the client list", () => {
  it("is most fixes first, then by name", () => {
    const sorted = sortClients([
      client("Delta", 0),
      client("Alpha", 1),
      client("Charlie", 2),
      client("Bravo", 1),
    ]);

    expect(names(sorted)).toEqual(["Charlie", "Alpha", "Bravo", "Delta"]);
  });

  it("never moves a client up for its advisory risks", () => {
    const sorted = sortClients([
      client("Many Risks", 0, 5),
      client("One Fix", 1, 0),
      client("Also No Fix", 0, 0),
      client("Unavailable", 0, 0, "unavailable"),
    ]);

    // One fix beats five risks; among clients with no fix only the name decides.
    expect(names(sorted)).toEqual(["One Fix", "Also No Fix", "Many Risks", "Unavailable"]);
  });

  it("gives the same order whatever the advisory counts are", () => {
    const base = [client("Echo", 2), client("Foxtrot", 0), client("Golf", 2), client("Hotel", 1)];
    const withRisks = base.map((entry, index) => client(entry.name, entry.today!.fixes, 5 - index));

    expect(names(sortClients(withRisks))).toEqual(names(sortClients(base)));
  });

  it("puts a client with no snapshot among those with nothing to fix, by name", () => {
    const sorted = sortClients([client("Zulu", null), client("Yankee", 0), client("Xray", 1)]);

    expect(names(sorted)).toEqual(["Xray", "Yankee", "Zulu"]);
  });

  it("orders the twelve seeded clients by fixes, then name", () => {
    const rows = clientRows(FALLBACK.clients, true);
    const fixes = rows.map((row) => row.fixes?.count ?? 0);

    expect(rows).toHaveLength(12);
    expect(fixes).toEqual([...fixes].sort((a, b) => b - a));
    expect(rows.slice(0, 3).map((row) => row.name)).toEqual([
      "Copperkettle Kitchen",
      "Emberglow Events",
      "Northwind Cycles",
    ]);
    expect(rows.at(-1)?.name).toBe("Willowmere Pet Supplies");
  });
});

describe("what a row says", () => {
  const list: ClientList = {
    day: "2026-11-20",
    clients: [
      client("Alpha", 1, 2),
      client("Bravo", 0, 0),
      client("Charlie", 3, 0, "unavailable"),
      client("Delta", null),
    ],
  };

  it("names its fixes, its advisory count and its snapshot", () => {
    const rows = clientRows(list, true);

    expect(
      rows.map((row) => [row.name, row.fixes?.text, row.advisory?.text, row.snapshot]),
    ).toEqual([
      ["Charlie", "3 fixes", "Risks unavailable", "Today"],
      ["Alpha", "1 fix", "2 advisory", "Today"],
      ["Bravo", "Nothing to fix", "No advisory", "Today"],
      ["Delta", undefined, undefined, "No snapshot today"],
    ]);
  });

  it("shows the date of a snapshot that is not today's", () => {
    expect(clientRows(list, false)[0].snapshot).toBe("20 Nov 2026");
  });

  it("has the chips' exact words", () => {
    expect([fixesText(0), fixesText(1), fixesText(2)]).toEqual([
      "Nothing to fix",
      "1 fix",
      "2 fixes",
    ]);
    expect(advisoryChip("ranked", 0)).toEqual({ kind: "none", text: "No advisory" });
    expect(advisoryChip("ranked", 2)).toEqual({ kind: "count", text: "2 advisory" });
    expect(advisoryChip("unavailable", 0)).toEqual({
      kind: "unavailable",
      text: "Risks unavailable",
    });
  });
});
