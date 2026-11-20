"use client";

// The pencil box: the model's risks, the "Mark handled" and "Reopen" buttons and the handled
// list. It always opens with the same three things: the heading, "Advisory, unproven." and the
// sentence with its link to the eval result.

import Link from "next/link";
import { type ReactElement, useEffect, useRef, useState } from "react";
import type { ClientPage, Risk } from "@/lib/api-types";
import {
  ADVISORY_HEADING,
  ADVISORY_MARK,
  ADVISORY_SENTENCE,
  ALL_RISKS_HANDLED,
  EVAL_LINK_TEXT,
  EVAL_PATH,
  NO_RISKS_TODAY,
  RISKS_UNAVAILABLE_TITLE,
  RISKS_UNAVAILABLE_WHY,
} from "@/lib/view/advisory";
import {
  type ClickAction,
  advisoryChipFor,
  afterClick,
  clickAnnouncement,
  handledItems,
  movedUpLine,
  ticksLine,
} from "@/lib/view/client-page";
import { basedOn } from "@/lib/view/evidence";
import type { Writes } from "@/lib/view/screens";
import { announce } from "./announcer";
import { DashCircle, EmptySquare, TickSquare } from "./icons";
import { AdvisoryChip, Banner } from "./parts";

const WHY_OFF: Partial<Record<Writes, string>> = {
  "old-day": "Handled can be marked on today's snapshot only.",
  fallback: "Marking handled is switched off while the live service cannot be reached.",
};

/** The three things every advisory box opens with, in the same words everywhere. */
export function AdvisoryOpening(): ReactElement {
  return (
    <div className="text-ink-2">
      <p className="font-medium">{ADVISORY_MARK}</p>
      <p className="measure mt-1">
        {ADVISORY_SENTENCE}{" "}
        <Link href={EVAL_PATH} className="link">
          {EVAL_LINK_TEXT}
        </Link>
      </p>
    </div>
  );
}

async function save(
  page: ClientPage,
  riskId: string,
  action: ClickAction,
): Promise<ClientPage | null> {
  try {
    const response = await fetch(`/api/clients/${page.id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ day: page.snapshot.day, risk_id: riskId }),
    });
    return response.ok ? ((await response.json()) as ClientPage) : null;
  } catch {
    return null;
  }
}

export interface AdvisoryPanelProps {
  page: ClientPage;
  writes: Writes;
  admin: boolean;
}

export function AdvisoryPanel({ page: initial, writes, admin }: AdvisoryPanelProps): ReactElement {
  const [page, setPage] = useState<ClientPage>(initial);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [moved, setMoved] = useState<string | null>(null);
  // Where focus goes once the lists have been redrawn: to "Reopen" after "Mark handled", and
  // back to the risk's "Mark handled" after "Reopen".
  const focusNext = useRef<string | null>(null);

  useEffect(() => {
    if (focusNext.current) {
      document.getElementById(focusNext.current)?.focus();
      focusNext.current = null;
    }
  });

  const off = WHY_OFF[writes] ?? null;
  const { snapshot } = page;
  const handled = handledItems(page);
  const movedLine = movedUpLine(page);
  const unavailable = snapshot.risks_status === "unavailable";

  async function click(risk: Risk, action: ClickAction): Promise<void> {
    if (off || busy) {
      return;
    }
    const before = page;
    // The click's own time; in a demo state the snapshot's day, so the dates shown do not move.
    const now = writes === "local" ? new Date(`${snapshot.day}T09:00:00Z`) : new Date();
    const next = afterClick(before, risk.id, action, now);
    focusNext.current = `${action === "handled" ? "reopen" : "mark"}-${risk.id}`;
    setFailed(false);
    setMoved(risk.id);
    setPage(next);
    announce(clickAnnouncement(next, risk.id, action));
    if (writes === "local") {
      return;
    }
    setBusy(true);
    const saved = await save(before, risk.id, action);
    setBusy(false);
    if (saved) {
      setPage(saved);
    } else {
      // Not saved: the change is undone and the page says so.
      setPage(before);
      setFailed(true);
      focusNext.current = `${action === "handled" ? "mark" : "reopen"}-${risk.id}`;
    }
  }

  return (
    <section aria-labelledby="advisory-heading" className="wide:col-span-5 wide:mt-8">
      <h2 id="advisory-heading" className="t-heading flex flex-wrap items-center gap-2">
        {ADVISORY_HEADING} <AdvisoryChip chip={advisoryChipFor(page)} />
      </h2>
      {failed ? (
        <div className="mt-3">
          <Banner
            tone="error"
            role="alert"
            title="That did not save, so nothing changed. Try again."
          />
        </div>
      ) : null}
      <div className="pencil mt-3">
        <AdvisoryOpening />
        {unavailable ? (
          <div className="hatch text-ink-3">
            <p className="flex items-center gap-2 font-medium">
              <DashCircle />
              {RISKS_UNAVAILABLE_TITLE}
            </p>
            <p className="measure mt-1">{RISKS_UNAVAILABLE_WHY}</p>
          </div>
        ) : snapshot.visible.length === 0 ? (
          <p className="measure text-ink-2">
            {handled.length > 0 ? ALL_RISKS_HANDLED : NO_RISKS_TODAY}
          </p>
        ) : (
          snapshot.visible.map((risk) => (
            <article key={risk.id} className={moved === risk.id ? "row-in" : undefined}>
              <h3 className="t-model-title text-ink-2">{risk.title}</h3>
              <p className="t-model mt-1 text-ink-2">{risk.why}</p>
              <p className="t-small mt-2 text-ink-3">{basedOn(risk.evidence)}</p>
              <button
                type="button"
                id={`mark-${risk.id}`}
                className="btn btn-secondary mt-3 w-full wide:w-auto"
                aria-disabled={off ? "true" : undefined}
                aria-describedby={off ? "handled-off" : undefined}
                onClick={() => void click(risk, "handled")}
              >
                <EmptySquare />
                Mark handled
              </button>
            </article>
          ))
        )}
      </div>
      {movedLine ? <p className="t-small mt-2 text-ink-3">{movedLine}</p> : null}
      {off && (snapshot.visible.length > 0 || handled.length > 0) ? (
        <p id="handled-off" className="t-small mt-2 text-ink-2">
          {off}
        </p>
      ) : null}
      {handled.length > 0 ? (
        <div className="mt-6">
          <h2 className="t-heading">Handled</h2>
          <p className="t-small mt-1 text-ink-3">{ticksLine(admin)}</p>
          <ul className="mt-3 border-t border-line">
            {handled.map(({ risk, dates }) => (
              <li
                key={risk.id}
                className={`flex flex-col gap-2 border-b border-line py-2 wide:flex-row wide:items-center wide:gap-4 ${moved === risk.id ? "row-in" : ""}`}
              >
                <p className="flex flex-1 items-start gap-2 text-ink-3">
                  <span className="mt-1">
                    <TickSquare />
                  </span>
                  <span>
                    <span className="t-model-title block line-through">{risk.title}</span>
                    <span className="t-small block">{dates}</span>
                  </span>
                </p>
                <button
                  type="button"
                  id={`reopen-${risk.id}`}
                  className="btn btn-secondary w-full wide:w-auto"
                  aria-disabled={off ? "true" : undefined}
                  aria-describedby={off ? "handled-off" : undefined}
                  aria-label={`Reopen: ${risk.title}`}
                  onClick={() => void click(risk, "reopen")}
                >
                  Reopen
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
