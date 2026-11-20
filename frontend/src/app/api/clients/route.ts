import { FALLBACK } from "@/lib/fallback";
import { loadClientList } from "@/lib/server/data";
import { json } from "@/lib/server/routes";

/** The client list as this visitor sees it, or the bundled one when the backend is away. */
export async function GET(): Promise<Response> {
  const load = await loadClientList();
  return load.kind === "ok"
    ? json(200, { source: "live", list: load.list })
    : json(200, { source: "fallback", list: FALLBACK.clients });
}
