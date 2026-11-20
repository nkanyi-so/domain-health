// Who a request acts as towards the backend: the admin (the shared list) or one visitor's sandbox.

import { ADMIN_COOKIE, VISITOR_COOKIE, verify } from "./session";

/**
 * The sandbox a visitor with no cookie reads through. Nothing is ever written to it: a write
 * first gives the visitor a session of their own, and a session id is sixteen random bytes.
 */
export const NO_SESSION = "0".repeat(32);

export interface Actor {
  /** The `X-Actor` header's value. */
  header: string;
  admin: boolean;
  /** The visitor's own sandbox id, when their cookie holds a valid one. */
  session: string | null;
}

export interface CookieValues {
  [name: string]: string | undefined;
}

export function sandboxActor(session: string): string {
  return `sandbox:${session}`;
}

/** Admin when the admin cookie is valid; otherwise the visitor's sandbox, or the empty one. */
export function chooseActor(cookies: CookieValues, secret: string | null, now: Date): Actor {
  if (!secret) {
    return { header: sandboxActor(NO_SESSION), admin: false, session: null };
  }
  const visitor = verify(cookies[VISITOR_COOKIE], "visitor", secret, now);
  const session = visitor ? visitor.id : null;
  if (verify(cookies[ADMIN_COOKIE], "admin", secret, now)) {
    return { header: "admin", admin: true, session };
  }
  return { header: sandboxActor(session ?? NO_SESSION), admin: false, session };
}
