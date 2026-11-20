import { FALLBACK } from "@/lib/fallback";
import { loadClientPage } from "@/lib/server/data";
import { buildReport, reportFileName, reportMarkdown } from "@/lib/view/report";
import { clientPageView } from "@/lib/view/screens";

function text(status: number, body: string): Response {
  return new Response(`${body}\n`, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/**
 * A client's report as Markdown, as this visitor sees the snapshot, or from the bundled one when
 * the backend is away. Read only: it makes the same load as the client page and writes nothing.
 */
export async function GET(
  request: Request,
  context: RouteContext<"/clients/[id]/report.md">,
): Promise<Response> {
  const { id } = await context.params;
  const view = clientPageView(await loadClientPage(id), FALLBACK);
  if (view.kind === "no-snapshot") {
    return text(404, "No snapshot for today yet, so there is no report.");
  }
  if (view.kind !== "snapshot") {
    return text(404, "No such client.");
  }
  const report = buildReport(view);
  // The eval link is written with this site's address, so it works from the saved file.
  const markdown = reportMarkdown(report, { baseUrl: new URL(request.url).origin });
  return new Response(markdown, {
    status: 200,
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="${reportFileName(report)}"`,
      // It is this visitor's own view (their handled ticks), so nothing in between keeps it.
      "Cache-Control": "private, no-store",
    },
  });
}
