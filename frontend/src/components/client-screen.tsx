// A client's page (`/clients/[id]`): fixes first, in ink; the model's advisory risks beside them,
// in pencil; then what was checked and the seeded figures.

import Link from "next/link";
import type { ReactElement } from "react";
import { isHealthy } from "@/lib/view/client-page";
import { checkRows } from "@/lib/view/checks";
import { promptNumber } from "@/lib/view/evals";
import { figures } from "@/lib/view/figures";
import { formatDay } from "@/lib/view/format";
import type { ClientPageView } from "@/lib/view/screens";
import { AdvisoryPanel } from "./advisory-panel";
import { FallbackStrip, PageFrame } from "./chrome";
import { Banner, type Fact, Facts, PlaceholderBar, SeededTag } from "./parts";
import { ChecksSection, FixesSection } from "./results";

function Breadcrumb(): ReactElement {
  return (
    <nav aria-label="Breadcrumb" className="t-small">
      <Link href="/" className="link tap">
        Clients
      </Link>
    </nav>
  );
}

function BackToClients(): ReactElement {
  return (
    <Link href="/" className="link tap">
      Back to clients
    </Link>
  );
}

function SeededLine(): ReactElement {
  return (
    <p className="t-small measure text-ink-2">
      Seeded client. Its figures and its DNS answers are made up for this demo.{" "}
      <Link href="/about" className="link">
        About this demo
      </Link>
    </p>
  );
}

function Loading(): ReactElement {
  return (
    <div aria-busy="true" className="flex flex-col gap-4">
      <p className="text-ink-2">Loading this client&apos;s snapshot</p>
      <div className="grid gap-8 wide:grid-cols-12">
        <div className="sheet flex flex-col gap-3 p-4 wide:col-span-7">
          <PlaceholderBar width="w-3/5" />
          <PlaceholderBar width="w-2/5" />
          <PlaceholderBar width="w-1/4" />
        </div>
        <div className="pencil wide:col-span-5 wide:mt-8">
          <div className="flex flex-col gap-3">
            <PlaceholderBar width="w-3/5" />
            <PlaceholderBar width="w-2/5" />
          </div>
        </div>
      </div>
    </div>
  );
}

export interface ClientScreenProps {
  view: ClientPageView;
  demo: string | null;
}

export function ClientScreen({ view, demo }: ClientScreenProps): ReactElement {
  if (view.kind === "loading") {
    return (
      <PageFrame demo={demo}>
        <div className="flex flex-col gap-4">
          <Breadcrumb />
          <Loading />
        </div>
      </PageFrame>
    );
  }
  if (view.kind === "no-such-client") {
    return (
      <PageFrame demo={demo}>
        <h1 className="t-title">No such client</h1>
        <p className="mt-2">There is no client at this address.</p>
        <p className="mt-2">
          <BackToClients />
        </p>
      </PageFrame>
    );
  }
  if (view.kind === "no-snapshot") {
    return (
      <PageFrame demo={demo}>
        <div className="flex flex-col gap-3">
          <Breadcrumb />
          <div>
            <h1 className="t-title">{view.client.name}</h1>
            <p className="t-mono text-ink-2">{view.client.domain}</p>
          </div>
          <SeededLine />
          <Banner tone="notice" title="No snapshot for today yet">
            <p>The daily run has not reached this client.</p>
            <p className="mt-1">
              <BackToClients />
            </p>
          </Banner>
        </div>
      </PageFrame>
    );
  }

  const { page, admin, writes } = view;
  const { snapshot } = page;
  const unavailable = snapshot.risks_status === "unavailable";
  const facts: Fact[] = [
    { label: "Snapshot", value: `${formatDay(snapshot.day)} (UTC)` },
    { label: "Prompt version", value: promptNumber(snapshot.prompt_version) },
    {
      label: "Model output",
      value: unavailable
        ? "Dropped: it did not pass its checks"
        : "Recorded from a real model run, not generated on this visit",
    },
  ];

  return (
    <PageFrame
      strip={view.fallbackDay ? <FallbackStrip day={view.fallbackDay} /> : null}
      demo={demo}
    >
      <div className="flex flex-col gap-3">
        <Breadcrumb />
        <div>
          <h1 className="t-title flex flex-wrap items-center gap-2">
            {page.name}
            {admin ? <span className="chip chip-admin">Admin</span> : null}
          </h1>
          <p className="t-mono text-ink-2">{snapshot.domain}</p>
        </div>
        <SeededLine />
        <Facts facts={facts} />
        {view.shownInsteadOfToday ? (
          <Banner tone="notice" title="No snapshot for today yet">
            <p>
              The daily run has not reached this client. Showing the latest one, from{" "}
              {formatDay(snapshot.day)}.
            </p>
          </Banner>
        ) : null}
        {isHealthy(page) ? (
          <Banner tone="ok" title="Healthy today">
            <p>Nothing to fix and no advisory risks.</p>
          </Banner>
        ) : null}
      </div>

      <div className="mt-8 grid gap-8 wide:grid-cols-12 wide:gap-x-8">
        <FixesSection
          fixes={snapshot.fixes}
          seeded={page.seeded}
          empty="Nothing to fix today. Every rule passed."
        />
        {/* Keyed by the snapshot, so a new day's page starts from what the server sent. */}
        <AdvisoryPanel
          key={`${page.id}-${snapshot.day}-${snapshot.finished_at}`}
          page={page}
          writes={writes}
          admin={admin}
        />
      </div>

      <div className="mt-8 flex flex-col gap-8 wide:mt-12 wide:gap-12">
        <ChecksSection rows={checkRows(snapshot.checks, snapshot.fixes)} tag="seeded" />
        <section aria-labelledby="figures-heading">
          <h2 id="figures-heading" className="t-heading">
            Figures
          </h2>
          <dl className="mt-3 grid border-b border-line wide:grid-cols-2 wide:gap-x-8">
            {figures(snapshot.sources).map((figure) => (
              <div
                key={figure.label}
                className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line py-3"
              >
                <dt className="flex items-center gap-2 text-ink-2">
                  {figure.label} <SeededTag />
                </dt>
                <dd className="text-ink">{figure.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </PageFrame>
  );
}
