// The shared chrome: header, admin bar, fallback strip, footer and the frame every page sits in.

import Link from "next/link";
import { type ReactElement, type ReactNode, Suspense } from "react";
import { FALLBACK } from "@/lib/fallback";
import { backendReachable, currentActor } from "@/lib/server/data";
import { repositoryUrl } from "@/lib/server/env";
import { demoNotice } from "@/lib/view/demo";
import { formatDay } from "@/lib/view/format";
import { fallbackNotice } from "@/lib/view/screens";
import { InfoCircle } from "./icons";
import { CurrentNav, NavLinks } from "./site-nav";
import { SignOutButton } from "./sign-out-button";
import { ThemeSwitch } from "./theme-switch";

/** Content is 1184 wide at most, 32 from the window's edge (16 on a phone), and left aligned. */
export const CONTAINER = "w-full max-w-content px-4 wide:px-8";

export function SiteHeader(): ReactElement {
  return (
    <header className="border-b border-line bg-page">
      <div className={`${CONTAINER} header-row flex flex-wrap items-center gap-x-6 py-2 wide:py-0`}>
        <Link href="/" className="wordmark tap order-1">
          domain-health
        </Link>
        <nav aria-label="Main" className="order-3 w-full wide:order-2 wide:w-auto">
          {/* On a client's page the address is not known until the request: no link is current. */}
          <Suspense fallback={<NavLinks current={null} />}>
            <CurrentNav />
          </Suspense>
        </nav>
        <div className="order-2 ml-auto wide:order-3">
          <ThemeSwitch />
        </div>
      </div>
    </header>
  );
}

/** Shown only to the signed-in admin, directly under the header. */
export async function AdminBar(): Promise<ReactElement | null> {
  const actor = await currentActor();
  if (!actor.admin) {
    return null;
  }
  return (
    <div className="strip">
      <div className={`${CONTAINER} flex flex-wrap items-center gap-x-4 gap-y-1 py-1 wide:py-0`}>
        <p className="flex items-start gap-2 py-2 wide:py-0">
          <span className="mt-1">
            <InfoCircle />
          </span>
          <span>
            Signed in as admin. Handled and reopen change the shared list that every visitor sees.
          </span>
        </p>
        <SignOutButton />
      </div>
    </div>
  );
}

/** State 15: the bundled snapshots are showing, and writes and the live check are off. */
export function FallbackStrip({ day }: { day: string }): ReactElement {
  return (
    <div className="strip" role="status">
      <div className={`${CONTAINER} flex items-start gap-2 py-3`}>
        <span className="mt-1">
          <InfoCircle />
        </span>
        <div className="measure">
          <p className="font-semibold text-notice">Showing saved data</p>
          <p>{fallbackNotice(day, formatDay)}</p>
        </div>
      </div>
    </div>
  );
}

async function StripIfAway(): Promise<ReactElement | null> {
  return (await backendReachable()) ? null : <FallbackStrip day={FALLBACK.generated_for_day} />;
}

/** For pages that load nothing else from the backend: asks whether it is there, and says if not. */
export function ServiceStrip(): ReactElement {
  return (
    <Suspense fallback={null}>
      <StripIfAway />
    </Suspense>
  );
}

function SiteFooter({ demo }: { demo: string | null }): ReactElement {
  const source = repositoryUrl();
  return (
    <footer className="mt-12 border-t border-line">
      <div className={`${CONTAINER} t-small flex flex-col gap-2 py-4 text-ink-3`}>
        {demo ? (
          <p className="rounded-sheet border border-notice-line bg-notice-wash px-3 py-2 text-ink">
            {demoNotice(demo)} Remove <code className="t-mono whitespace-nowrap">?demo</code> from
            the address for live data.
          </p>
        ) : null}
        <p>A public rebuild on seeded data. The twelve clients are invented.</p>
        <ul className="flex flex-wrap gap-x-6">
          <li>
            <Link href="/about" className="link tap">
              About this demo
            </Link>
          </li>
          {source ? (
            <li>
              <a href={source} className="link tap">
                Source
              </a>
            </li>
          ) : null}
          <li>
            <Link href="/admin" className="link tap">
              Admin sign-in
            </Link>
          </li>
        </ul>
      </div>
    </footer>
  );
}

export interface PageFrameProps {
  /** A strip across the window, under the header: the fallback notice. */
  strip?: ReactNode;
  /** The demo state being drawn, named in the footer. */
  demo?: string | null;
  children: ReactNode;
}

export function PageFrame({ strip, demo, children }: PageFrameProps): ReactElement {
  return (
    <>
      {strip}
      <main id="content" tabIndex={-1} className={`${CONTAINER} flex-1 py-8 outline-none`}>
        {children}
      </main>
      <SiteFooter demo={demo ?? null} />
    </>
  );
}
