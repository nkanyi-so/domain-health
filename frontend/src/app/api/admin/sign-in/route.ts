import { headers } from "next/headers";
import { ConfigError, sessionSecretOrNull, setting } from "@/lib/server/env";
import { attempt, signInLimiter } from "@/lib/server/rate-limit";
import { clientAddress } from "@/lib/server/request";
import { bodyOf, crossSite, issueSession, json } from "@/lib/server/routes";
import { sameSecret } from "@/lib/server/session";

const MAX_PASSPHRASE = 500;

/**
 * Admin sign-in. The passphrase is compared in constant time; wrong tries are counted per address
 * and overall (`lib/server/rate-limit.ts`), and the answer never says how close a try was.
 */
export async function POST(request: Request): Promise<Response> {
  const refused = crossSite(request);
  if (refused) {
    return refused;
  }
  const secret = sessionSecretOrNull();
  let expected: string;
  try {
    expected = setting("ADMIN_PASSPHRASE");
  } catch (error) {
    if (error instanceof ConfigError) {
      return json(503, { error: "unavailable" });
    }
    throw error;
  }
  if (!secret) {
    return json(503, { error: "unavailable" });
  }
  // Everything that waits comes first, so the attempt itself is one uninterrupted step.
  const address = clientAddress(await headers());
  const body = await bodyOf(request);
  const given = body?.passphrase;
  const outcome = attempt(
    signInLimiter,
    address,
    Date.now(),
    () =>
      typeof given === "string" &&
      given.length <= MAX_PASSPHRASE &&
      sameSecret(given, expected, secret),
  );
  if (outcome === "limited") {
    return json(429, { error: "too many tries" });
  }
  if (outcome === "wrong") {
    return json(401, { error: "wrong" });
  }
  await issueSession("admin");
  return json(200, { ok: true });
}
