import { FALLBACK } from "@/lib/fallback";
import { loadClientPage } from "@/lib/server/data";
import { json } from "@/lib/server/routes";

/** Today's page for one client as this visitor sees it, or the bundled one when the backend is away. */
export async function GET(
  _request: Request,
  context: RouteContext<"/api/clients/[id]/snapshot">,
): Promise<Response> {
  const { id } = await context.params;
  const { today } = await loadClientPage(id);
  switch (today.kind) {
    case "ok":
      return json(200, { source: "live", page: today.page });
    case "no-snapshot":
      return json(404, { error: "no snapshot for that day" });
    case "no-such-client":
      return json(404, { error: "no such client" });
    case "unreachable":
      return Object.hasOwn(FALLBACK.snapshots, id)
        ? json(200, { source: "fallback", page: FALLBACK.snapshots[id] })
        : json(404, { error: "no such client" });
  }
}
