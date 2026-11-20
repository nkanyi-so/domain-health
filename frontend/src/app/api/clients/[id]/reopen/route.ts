import { click } from "@/lib/server/click";

export async function POST(
  request: Request,
  context: RouteContext<"/api/clients/[id]/reopen">,
): Promise<Response> {
  const { id } = await context.params;
  return click(request, id, "reopen");
}
