// "Mark handled" and "Reopen": one handler for the two routes.

import { WRITE_TIMEOUT_MS, detailOf } from "./backend";
import { bodyOf, crossSite, json, send, writingActor } from "./routes";

const CLIENT_ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

export async function click(
  request: Request,
  clientId: string,
  action: "handled" | "reopen",
): Promise<Response> {
  const refused = crossSite(request);
  if (refused) {
    return refused;
  }
  const body = await bodyOf(request);
  const day = body?.day;
  const riskId = body?.risk_id;
  if (
    !CLIENT_ID.test(clientId) ||
    clientId.length > 64 ||
    typeof day !== "string" ||
    !DAY.test(day) ||
    typeof riskId !== "string" ||
    riskId.length === 0 ||
    riskId.length > 200
  ) {
    return json(400, { error: "bad request" });
  }
  const actor = await writingActor();
  if (!actor) {
    return json(503, { error: "unavailable" });
  }
  const answer = await send({
    method: "POST",
    path: `/api/clients/${clientId}/${action}`,
    actor,
    body: { day, risk_id: riskId },
    timeoutMs: WRITE_TIMEOUT_MS,
  });
  if (answer.kind === "ok") {
    return json(200, answer.body);
  }
  if (answer.kind === "refused") {
    // 404 no snapshot that day, 422 no such risk that day: passed on as they are.
    const status = answer.status === 404 || answer.status === 422 ? answer.status : 502;
    return json(status, { error: detailOf(answer.body) ?? "refused" });
  }
  return json(503, { error: "unreachable" });
}
