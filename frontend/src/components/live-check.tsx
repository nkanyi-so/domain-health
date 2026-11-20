"use client";

// The live check (`/check`): the form and whatever the check came back with. The check itself is
// a POST to this site's own route, made from here once the page is open, so that opening or
// prefetching an address never spends one of a visitor's five checks.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactElement, useEffect, useRef, useState } from "react";
import type { LiveCheckResult } from "@/lib/api-types";
import { checkRows } from "@/lib/view/checks";
import { formatTime } from "@/lib/view/format";
import {
  type LiveCheckView,
  NO_LOOKUP,
  REFUSAL_TITLE,
  finishedAnnouncement,
  liveCheckView,
  lookingUp,
} from "@/lib/view/live-check";
import { announce } from "./announcer";
import { Banner, Facts } from "./parts";
import { ChecksLookingUp, ChecksSection, FixesSection } from "./results";

/**
 * `live`: checks are made. `demo`: a fixed state is drawn and nothing is sent. `off`: the
 * backend cannot be reached, so the check is switched off.
 */
export type LiveCheckMode = "live" | "demo" | "off";

export interface LiveCheckProps {
  initialDomain: string;
  mode: LiveCheckMode;
  /** The state to draw in demo mode. */
  demoView?: LiveCheckView;
}

function firstView(props: LiveCheckProps): LiveCheckView {
  if (props.mode === "demo" && props.demoView) {
    return props.demoView;
  }
  if (props.mode === "off") {
    return { kind: "switched-off" };
  }
  return props.initialDomain ? { kind: "running", domain: props.initialDomain } : { kind: "idle" };
}

async function check(domain: string): Promise<LiveCheckView> {
  try {
    const response = await fetch("/api/live-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain }),
    });
    const body: unknown = await response.json().catch(() => null);
    return liveCheckView(response.status, body, domain, new Date());
  } catch {
    return { kind: "failed" };
  }
}

function SeeClients(): ReactElement {
  return (
    <Link href="/" className="link">
      See the clients
    </Link>
  );
}

function Result({
  result,
  ageLine,
}: {
  result: LiveCheckResult;
  ageLine: string | null;
}): ReactElement {
  const rows = checkRows(result.checks, result.fixes);
  const allMade = rows.every((row) => row.state !== "not-made");
  return (
    <div className="flex flex-col gap-8 wide:gap-12">
      <div className="flex flex-col gap-3">
        <h2 className="t-title t-mono flex flex-wrap items-center gap-2">
          {result.domain}
          <span className="chip chip-live">Live DNS</span>
        </h2>
        <Facts
          facts={[
            { label: "Checked", value: formatTime(result.checked_at) },
            { label: "Model output", value: "none for a typed domain" },
          ]}
        />
        {ageLine ? <p className="t-small text-ink-2">{ageLine}</p> : null}
      </div>
      <div className="grid gap-8 wide:grid-cols-12 wide:gap-x-8">
        <FixesSection
          fixes={result.fixes}
          seeded={false}
          empty={
            allMade
              ? "Nothing to fix. SPF, DKIM and DMARC all passed these checks."
              : "Nothing to fix from the checks that could be made."
          }
        />
        <section aria-labelledby="advisory-heading" className="wide:col-span-5 wide:mt-8">
          <h2 id="advisory-heading" className="t-heading">
            Advisory risks
          </h2>
          <div className="pencil mt-3">
            <p className="measure text-ink-2">
              None for a typed domain. Advisory risks need reputation and sending figures, and this
              demo has those for its seeded clients only.{" "}
              <Link href="/" className="link">
                See a seeded client
              </Link>
            </p>
          </div>
        </section>
      </div>
      <ChecksSection rows={rows} tag="live" />
    </div>
  );
}

export function LiveCheck(props: LiveCheckProps): ReactElement {
  const { mode } = props;
  const [typed, setTyped] = useState(props.initialDomain);
  const [view, setView] = useState<LiveCheckView>(() => firstView(props));
  const started = useRef(false);
  const router = useRouter();

  async function run(domain: string): Promise<void> {
    setView({ kind: "running", domain });
    announce(lookingUp(domain));
    const next = await check(domain);
    setView(next);
    if (next.kind === "result") {
      announce(finishedAnnouncement(next.result));
    }
  }

  // An address that names a domain starts its check once, when the page opens.
  useEffect(() => {
    if (mode === "live" && props.initialDomain && !started.current) {
      started.current = true;
      void check(props.initialDomain).then((next) => {
        setView(next);
        if (next.kind === "result") {
          announce(finishedAnnouncement(next.result));
        }
      });
    }
  }, [mode, props.initialDomain]);

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const domain = typed.trim();
    if (!domain || view.kind === "running") {
      return;
    }
    if (mode !== "live") {
      // A demo state never sends anything: leave it for the real page.
      if (mode === "demo") {
        router.push(`/check?domain=${encodeURIComponent(domain)}`);
      }
      return;
    }
    window.history.replaceState(null, "", `/check?domain=${encodeURIComponent(domain)}`);
    void run(domain);
  }

  const running = view.kind === "running";
  const refused = view.kind === "refused";
  const closed = view.kind === "cap-reached" || view.kind === "switched-off";
  const describedBy = [refused ? "check-refused" : null, "check-hint"].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={submit} noValidate>
        <label htmlFor="domain" className="t-small font-medium">
          Domain
        </label>
        <div className="mt-1 flex flex-col gap-2 wide:flex-row wide:items-center">
          <input
            id="domain"
            name="domain"
            type="text"
            className="field wide:max-w-field"
            placeholder="example.com"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={300}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            readOnly={running || closed}
            aria-invalid={refused ? "true" : undefined}
            aria-describedby={describedBy}
          />
          {running || closed ? (
            <button type="button" className="btn btn-primary" aria-disabled="true">
              {running ? "Checking" : "Check domain"}
            </button>
          ) : (
            <button type="submit" className="btn btn-primary">
              Check domain
            </button>
          )}
        </div>
        <p id="check-hint" className="t-small mt-2 text-ink-3">
          Five checks per ten minutes. Results are kept for ten minutes.
        </p>
        {view.kind === "switched-off" ? (
          <p className="t-small mt-2 text-ink-2">
            Switched off while the live service cannot be reached.
          </p>
        ) : null}
      </form>

      {running ? (
        <>
          <p className="measure">{lookingUp(view.domain)} This takes a few seconds.</p>
          <ChecksLookingUp />
        </>
      ) : null}

      {view.kind === "refused" ? (
        <Banner tone="error" role="alert" id="check-refused" title={REFUSAL_TITLE}>
          <p>{view.message}</p>
          <p>{NO_LOOKUP}</p>
        </Banner>
      ) : null}

      {view.kind === "rate-limited" ? (
        <Banner tone="notice" role="alert" title="Five checks in ten minutes is the limit">
          <p>
            Wait a few minutes and try again. The seeded clients are not limited. <SeeClients />
          </p>
        </Banner>
      ) : null}

      {view.kind === "cap-reached" ? (
        <Banner tone="notice" role="alert" title="Today's 200 checks are used up">
          <p>
            This demo stops at 200 live checks a day. It opens again at 00:00 UTC. The seeded
            clients still work. <SeeClients />
          </p>
        </Banner>
      ) : null}

      {view.kind === "failed" ? (
        <Banner tone="error" role="alert" title="That check did not finish">
          <p>Something went wrong on our side. Try again.</p>
        </Banner>
      ) : null}

      {view.kind === "result" ? <Result result={view.result} ageLine={view.ageLine} /> : null}
    </div>
  );
}
