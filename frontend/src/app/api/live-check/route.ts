import { headers } from "next/headers";
import { LIVE_CHECK_TIMEOUT_MS, detailOf } from "@/lib/server/backend";
import { clientAddress } from "@/lib/server/request";
import { bodyOf, crossSite, json, requestActor, send } from "@/lib/server/routes";

const MAX_TYPED = 300;

/**
 * A live check of a typed domain. A POST with this site's own `Origin` only, so no link, crawler
 * or prefetch can spend a visitor's checks. The backend validates the name and holds the limits;
 * this adds the proxy secret, the actor and the one address the platform reports.
 */
export async function POST(request: Request): Promise<Response> {
  const refused = crossSite(request);
  if (refused) {
    return refused;
  }
  const body = await bodyOf(request);
  const domain = body?.domain;
  if (typeof domain !== "string") {
    return json(400, { error: "bad request" });
  }
  if (domain.length > MAX_TYPED) {
    return json(422, { refused: "too_long" });
  }
  const actor = await requestActor();
  const answer = await send({
    method: "POST",
    path: "/api/live-check",
    actor: actor.header,
    body: { domain },
    clientAddress: clientAddress(await headers()),
    timeoutMs: LIVE_CHECK_TIMEOUT_MS,
  });
  if (answer.kind === "ok") {
    return json(200, answer.body);
  }
  if (answer.kind === "unreachable") {
    return json(503, { error: "unreachable" });
  }
  const detail = detailOf(answer.body);
  const reason =
    typeof detail === "object" && detail !== null
      ? (detail as Record<string, unknown>).refused
      : null;
  if (answer.status === 422) {
    return json(422, { refused: typeof reason === "string" ? reason : "not_a_name" });
  }
  if (answer.status === 429) {
    return json(429, { refused: reason === "daily_cap" ? "daily_cap" : "rate_limited" });
  }
  return json(502, { error: "failed" });
}
