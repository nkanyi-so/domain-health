// What the pages read, fetched on the server. Pages call these directly; they never call this
// site's own route handlers over HTTP. Each is remembered for the length of one request, so the
// banner and the table of one page share one call.

import { cache } from "react";
import type { ClientList, ClientPage } from "../api-types";
import { addDays, utcDay } from "../view/format";
import type { ClientPageLoads, ListLoad, PageLoad } from "../view/screens";
import type { Actor } from "./actor";
import { type BackendAnswer, READ_TIMEOUT_MS, callBackend, detailOf } from "./backend";
import { ConfigError, backendConfig } from "./env";
import { requestActor } from "./routes";

const CLIENT_ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** Who this request is, worked out once for the request. */
export const currentActor: () => Promise<Actor> = cache(requestActor);

/** A read of the backend as whoever this request is. With no backend settings it is away. */
export async function read(
  path: string,
  timeoutMs: number = READ_TIMEOUT_MS,
): Promise<BackendAnswer> {
  const actor = await currentActor();
  try {
    return await callBackend(backendConfig(), {
      method: "GET",
      path,
      actor: actor.header,
      timeoutMs,
    });
  } catch (error) {
    if (error instanceof ConfigError) {
      console.error(`backend settings: ${error.message}`);
      return { kind: "unreachable", why: "not configured" };
    }
    throw error;
  }
}

function refusedError(path: string, answer: { status: number }): Error {
  return new Error(`the backend refused GET ${path} with ${answer.status}`);
}

export const loadClientList: () => Promise<ListLoad> = cache(async (): Promise<ListLoad> => {
  const answer = await read("/api/clients");
  if (answer.kind === "unreachable") {
    return { kind: "unreachable" };
  }
  if (answer.kind === "refused") {
    throw refusedError("/api/clients", answer);
  }
  const list = answer.body as ClientList;
  return Array.isArray(list.clients) ? { kind: "ok", list } : { kind: "unreachable" };
});

async function loadDay(id: string, day: string | null): Promise<PageLoad> {
  const path = `/api/clients/${encodeURIComponent(id)}/snapshot${day ? `?day=${day}` : ""}`;
  const answer = await read(path);
  if (answer.kind === "unreachable") {
    return { kind: "unreachable" };
  }
  if (answer.kind === "refused") {
    if (answer.status === 404) {
      return detailOf(answer.body) === "no such client"
        ? { kind: "no-such-client" }
        : { kind: "no-snapshot" };
    }
    throw refusedError(path, answer);
  }
  const page = answer.body as ClientPage;
  return typeof page.snapshot === "object" ? { kind: "ok", page } : { kind: "unreachable" };
}

/**
 * A client's page for today. When today has no snapshot yet, the day before is asked for once,
 * so the page can show the latest one and say so.
 */
export const loadClientPage: (id: string) => Promise<ClientPageLoads> = cache(
  async (id: string): Promise<ClientPageLoads> => {
    const actor = await currentActor();
    if (!CLIENT_ID.test(id) || id.length > 64) {
      return { id, today: { kind: "no-such-client" }, earlier: null, admin: actor.admin };
    }
    const today = await loadDay(id, null);
    const earlier =
      today.kind === "no-snapshot" ? await loadDay(id, addDays(utcDay(new Date()), -1)) : null;
    return { id, today, earlier, admin: actor.admin };
  },
);

/** Can the backend be reached right now? For the pages that load nothing else from it. */
export const backendReachable: () => Promise<boolean> = cache(async (): Promise<boolean> => {
  const answer = await read("/health");
  return answer.kind !== "unreachable";
});
