// One call to the backend. The browser never makes this call: only the server does, adding the
// proxy secret, the actor and, for the live check, the visitor's address.

import type { BackendConfig } from "./env";

// Long enough for a service that scales to nothing to start; the loading state covers the wait.
export const READ_TIMEOUT_MS = 12_000;
/** A click is a transaction that may be retried a few times. */
export const WRITE_TIMEOUT_MS = 15_000;
/** A live check may spend eight seconds on each of three checks. */
export const LIVE_CHECK_TIMEOUT_MS = 30_000;

export interface BackendRequest {
  method: "GET" | "POST";
  path: string;
  actor: string;
  body?: unknown;
  clientAddress?: string;
  timeoutMs: number;
}

/**
 * What came back. `refused` is any 4xx: the backend answered and said no, which is not the same
 * as the backend being away. `unreachable` is a network error, a timeout or any 5xx.
 */
export type BackendAnswer =
  | { kind: "ok"; status: number; body: unknown }
  | { kind: "refused"; status: number; body: unknown }
  | { kind: "unreachable"; why: string };

export type Fetch = (input: string, init: RequestInit) => Promise<Response>;

async function jsonOrNull(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function callBackend(
  config: BackendConfig,
  request: BackendRequest,
  fetchImpl: Fetch = fetch,
): Promise<BackendAnswer> {
  const headers: Record<string, string> = {
    "X-Proxy-Secret": config.proxySecret,
    "X-Actor": request.actor,
    Accept: "application/json",
  };
  if (request.clientAddress !== undefined) {
    headers["X-Client-Address"] = request.clientAddress;
  }
  if (request.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  let response: Response;
  try {
    response = await fetchImpl(`${config.url}${request.path}`, {
      method: request.method,
      headers,
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(request.timeoutMs),
    });
  } catch (error) {
    const name = error instanceof Error ? error.name : "";
    return { kind: "unreachable", why: name === "TimeoutError" ? "timeout" : "network" };
  }
  if (response.status >= 200 && response.status < 300) {
    const body = await jsonOrNull(response);
    // A 2xx that is not JSON did not come from the backend's own code.
    return body === null
      ? { kind: "unreachable", why: "not json" }
      : { kind: "ok", status: response.status, body };
  }
  if (response.status >= 400 && response.status < 500) {
    return { kind: "refused", status: response.status, body: await jsonOrNull(response) };
  }
  return { kind: "unreachable", why: `status ${response.status}` };
}

/** The `detail` of a backend error body: a word, or an object such as `{refused, why}`. */
export function detailOf(body: unknown): unknown {
  if (typeof body === "object" && body !== null && "detail" in body) {
    return (body as { detail: unknown }).detail;
  }
  return null;
}
