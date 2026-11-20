"use client";

// The first screen's "Check any domain" form. Pressing the button leaves a marker for this tab
// and goes to `/check?domain=<typed>`, where the marker lets the check start at once. Without
// scripts it is a plain form that lands on the same address with the field filled.

import { useRouter } from "next/navigation";
import type { FormEvent, ReactElement } from "react";
import { leaveStart } from "@/lib/view/live-check";

const SWITCHED_OFF = "Switched off while the live service cannot be reached.";

/** Leave word that the visitor asked for this domain, then open the check page for it. */
export function startCheck(domain: string, go: (address: string) => void): void {
  try {
    leaveStart(window.sessionStorage, domain, Date.now());
  } catch {
    // Storage can be switched off; the check page then waits for a second press.
  }
  go(`/check?domain=${encodeURIComponent(domain)}`);
}

export function CheckForm({ off }: { off: boolean }): ReactElement {
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const field = event.currentTarget.elements.namedItem("domain");
    const domain = field instanceof HTMLInputElement ? field.value.trim() : "";
    if (off || !domain) {
      return;
    }
    startCheck(domain, (address) => router.push(address));
  }

  return (
    <section aria-labelledby="check-heading">
      <h2 id="check-heading" className="t-heading">
        Check any domain
      </h2>
      <form action="/check" method="get" className="mt-3" onSubmit={submit}>
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
            aria-describedby={off ? "check-hint check-off" : "check-hint"}
          />
          {off ? (
            <button type="button" className="btn btn-primary" aria-disabled="true">
              Check domain
            </button>
          ) : (
            <button type="submit" className="btn btn-primary">
              Check domain
            </button>
          )}
          <p id="check-hint" className="t-small text-ink-3">
            Real DNS lookups for SPF, DKIM and DMARC. No sign-in.
          </p>
        </div>
        {off ? (
          <p id="check-off" className="t-small mt-2 text-ink-2">
            {SWITCHED_OFF}
          </p>
        ) : null}
      </form>
    </section>
  );
}
