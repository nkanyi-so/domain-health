// The snapshots bundled with the page, for when the backend cannot be reached. Written by
// `make fallback` (a backend test fails when the file is stale): the bodies of the two read
// routes for the twelve seeded clients on one fixed day.

import raw from "@/data/fallback.json";
import type { ClientList, ClientPage } from "./api-types";

export interface FallbackData {
  generated_for_day: string;
  clients: ClientList;
  snapshots: Record<string, ClientPage>;
}

// The JSON's own type says "string" where the API's says which strings; the backend's test checks
// the file against the API's models, and a test here checks its shape.
export const FALLBACK: FallbackData = raw as unknown as FallbackData;
