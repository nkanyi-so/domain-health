import type { Metadata } from "next";
import Link from "next/link";
import { type ReactElement, Suspense } from "react";
import { FallbackStrip, PageFrame } from "@/components/chrome";
import { ClientScreen } from "@/components/client-screen";
import { Banner } from "@/components/parts";
import { ReportDocument } from "@/components/report";
import { FALLBACK } from "@/lib/fallback";
import { loadClientPage } from "@/lib/server/data";
import { buildReport } from "@/lib/view/report";
import { clientPageView } from "@/lib/view/screens";

type Props = PageProps<"/clients/[id]/report">;

/** The twelve seeded clients are known when the page is built. */
export function generateStaticParams(): { id: string }[] {
  return FALLBACK.clients.clients.map((client) => ({ id: client.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const client = FALLBACK.clients.clients.find((entry) => entry.id === id);
  return { title: client ? `${client.name} report` : "No such client" };
}

function BackToClient({ id, name }: { id: string; name: string }): ReactElement {
  return (
    <nav aria-label="Breadcrumb" className="t-small no-print">
      <Link href={`/clients/${id}`} className="link tap">
        {name}
      </Link>
    </nav>
  );
}

/** Read only: the same load the client page makes, and nothing is written. */
async function ClientReport({ params }: Props): Promise<ReactElement> {
  const { id } = await params;
  const view = clientPageView(await loadClientPage(id), FALLBACK);
  if (view.kind === "loading" || view.kind === "no-such-client") {
    return <ClientScreen view={{ kind: "no-such-client" }} demo={null} />;
  }
  if (view.kind === "no-snapshot") {
    return (
      <PageFrame>
        <div className="flex flex-col gap-3">
          <BackToClient id={view.client.id} name={view.client.name} />
          <h1 className="t-title">Domain health report: {view.client.name}</h1>
          <Banner tone="notice" title="No snapshot for today yet">
            <p>
              The daily run has not reached this client, so there is nothing to report. No report
              was made.
            </p>
          </Banner>
        </div>
      </PageFrame>
    );
  }
  const report = buildReport(view);
  return (
    <PageFrame strip={view.fallbackDay ? <FallbackStrip day={view.fallbackDay} /> : null}>
      <div className="no-print mb-8 flex flex-col gap-3">
        <BackToClient id={view.page.id} name={view.page.name} />
        <p className="flex flex-col gap-2 wide:flex-row wide:items-center wide:gap-4">
          {/* A route handler, not a page: a plain link, so the browser saves the file. */}
          <a
            href={`/clients/${view.page.id}/report.md`}
            download
            className="btn btn-secondary w-full wide:w-auto"
          >
            Download as Markdown
          </a>
          <span className="t-small text-ink-3">
            To keep it as a PDF, print this page: the header, footer and buttons are left out.
          </span>
        </p>
      </div>
      <ReportDocument report={report} />
    </PageFrame>
  );
}

function Loading(): ReactElement {
  return (
    <PageFrame>
      <p aria-busy="true" className="text-ink-2">
        Loading this client&apos;s report
      </p>
    </PageFrame>
  );
}

export default function Page(props: Props): ReactElement {
  return (
    <Suspense fallback={<Loading />}>
      <ClientReport {...props} />
    </Suspense>
  );
}
