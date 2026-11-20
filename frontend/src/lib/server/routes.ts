// Shared by the route handlers under `app/api/`: the origin check on writes, who the caller acts
// as, and the visitor's session cookie, made the first time a write needs it.

import { cookies, headers } from "next/headers";
import { connection } from "next/server";
import { type Actor, chooseActor, sandboxActor } from "./actor";
import { type BackendAnswer, type BackendRequest, callBackend } from "./backend";
import { ConfigError, backendConfig, sessionSecretOrNull } from "./env";
import { sameOrigin } from "./request";
import {
  ADMIN_COOKIE,
  type SessionKind,
  VISITOR_COOKIE,
  cookieOptions,
  lifetime,
  secureCookies,
  sign,
  startSession,
} from "./session";

export function json(status: number, body: unknown): Response {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

/** A write from any other site, or with no `Origin` at all, is refused. */
export function crossSite(request: Request): Response | null {
  return sameOrigin(request.headers.get("origin"), request.headers.get("host"))
    ? null
    : json(403, { error: "origin" });
}

export async function requestActor(): Promise<Actor> {
  const jar = await cookies();
  // A session is judged against the clock, so this is worked out per request and never ahead.
  await connection();
  return chooseActor(
    {
      [VISITOR_COOKIE]: jar.get(VISITOR_COOKIE)?.value,
      [ADMIN_COOKIE]: jar.get(ADMIN_COOKIE)?.value,
    },
    sessionSecretOrNull(),
    new Date(),
  );
}

async function secure(): Promise<boolean> {
  const sent = await headers();
  return secureCookies(sent.get("host"), sent.get("x-forwarded-proto"));
}

/** Starts a session of this kind and sets its cookie. Null when there is no session secret. */
export async function issueSession(kind: SessionKind): Promise<string | null> {
  const secret = sessionSecretOrNull();
  if (!secret) {
    return null;
  }
  const session = startSession(kind, new Date());
  const name = kind === "admin" ? ADMIN_COOKIE : VISITOR_COOKIE;
  (await cookies()).set(name, sign(session, secret), cookieOptions(await secure(), lifetime(kind)));
  return session.id;
}

export async function clearAdminSession(): Promise<void> {
  (await cookies()).set(ADMIN_COOKIE, "", cookieOptions(await secure(), 0));
}

/**
 * The `X-Actor` value for a write: the admin, or the visitor's own sandbox, which is given a
 * session now if it has none. Null when no session can be made (no secret): the write is refused.
 */
export async function writingActor(): Promise<string | null> {
  const actor = await requestActor();
  if (actor.admin) {
    return actor.header;
  }
  const session = actor.session ?? (await issueSession("visitor"));
  return session ? sandboxActor(session) : null;
}

/** One call to the backend; a server with no backend settings reads as a backend that is away. */
export async function send(request: BackendRequest): Promise<BackendAnswer> {
  try {
    return await callBackend(backendConfig(), request);
  } catch (error) {
    if (error instanceof ConfigError) {
      console.error(`backend settings: ${error.message}`);
      return { kind: "unreachable", why: "not configured" };
    }
    throw error;
  }
}

export async function bodyOf(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const parsed: unknown = await request.json();
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}
