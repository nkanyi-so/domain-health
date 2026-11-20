import Link from "next/link";
import type { ReactElement } from "react";
import { CLAIM } from "@/content/claim";
import { LIMIT } from "@/content/limit";

/**
 * The claim and its limit, always together in one ruled block: side by side at the wide
 * breakpoint, the limit directly under the claim on a phone. The limit is in the same ink.
 */
export function ClaimBlock(): ReactElement {
  return (
    <section
      aria-label="What this is, and its limit"
      className="grid gap-4 border-t border-line-strong pt-4 wide:grid-cols-12 wide:gap-x-8"
    >
      <div className="wide:col-span-7">
        <p className="t-small text-ink-3">What this is</p>
        <p className="t-lead measure mt-1 text-ink">{CLAIM}</p>
      </div>
      <div className="wide:col-span-5">
        <p className="t-small text-ink-3">Its limit</p>
        <p className="t-body mt-1 text-ink">
          {LIMIT}{" "}
          <Link href="/evals" className="link">
            See the eval result
          </Link>
        </p>
      </div>
    </section>
  );
}
