// The client list (`/`): the claim with its limit, the live-check field, then the twelve clients.

import Link from "next/link";
import type { ReactElement } from "react";
import type { ClientRow } from "@/lib/view/clients";
import type { ClientListView } from "@/lib/view/screens";
import { CheckForm } from "./check-form";
import { FallbackStrip, PageFrame } from "./chrome";
import { ClaimBlock } from "./claim-block";
import { AdvisoryChip, FixesChip, PlaceholderBar } from "./parts";

function Chips({ row }: { row: ClientRow }): ReactElement | null {
  if (!row.fixes || !row.advisory) {
    return null;
  }
  return (
    <>
      <FixesChip count={row.fixes.count} />
      <AdvisoryChip chip={row.advisory} />
    </>
  );
}

/** A real table at the wide breakpoint; the whole row is the link's hit area. */
function WideTable({ rows }: { rows: readonly ClientRow[] }): ReactElement {
  return (
    <table className="mt-3 hidden w-full table-fixed border-collapse text-left wide:table">
      <colgroup>
        <col />
        <col className="col-chip" />
        <col className="col-chip" />
        <col className="col-snapshot" />
      </colgroup>
      <thead>
        <tr className="t-small bg-sunk text-ink-2">
          <th scope="col" className="px-4 py-2 font-medium">
            Client
          </th>
          <th scope="col" className="px-4 py-2 font-medium">
            Fixes
          </th>
          <th scope="col" className="px-4 py-2 font-medium">
            Advisory
          </th>
          <th scope="col" className="px-4 py-2 font-medium">
            Snapshot
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className="client-row border-b border-line">
            <th scope="row" className="px-4 py-2 font-normal">
              <Link href={`/clients/${row.id}`} className="font-semibold text-ink">
                {row.name}
              </Link>
              <span className="t-small t-mono block text-ink-3">{row.domain}</span>
            </th>
            <td className="px-4 py-2">
              {row.fixes ? <FixesChip count={row.fixes.count} /> : null}
            </td>
            <td className="px-4 py-2">
              {row.advisory ? <AdvisoryChip chip={row.advisory} /> : null}
            </td>
            <td className="t-small px-4 py-2 text-ink-2">{row.snapshot}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** On a phone: no header row, three short lines per client. */
function NarrowList({ rows }: { rows: readonly ClientRow[] }): ReactElement {
  return (
    <ul className="mt-3 border-t border-line wide:hidden">
      {rows.map((row) => (
        <li key={row.id} className="client-row flex flex-col gap-1 border-b border-line px-4 py-3">
          <Link href={`/clients/${row.id}`} className="font-semibold text-ink">
            {row.name}
          </Link>
          <span className="t-small t-mono text-ink-3">{row.domain}</span>
          <span className="flex flex-wrap gap-2">
            <Chips row={row} />
          </span>
          <span className="t-small text-ink-2">Snapshot: {row.snapshot}</span>
        </li>
      ))}
    </ul>
  );
}

/** State 1: six placeholder rows where the table will be. */
function LoadingRows(): ReactElement {
  return (
    <div aria-busy="true" className="mt-3">
      <p className="text-ink-2">Loading today&apos;s snapshots</p>
      <ul className="mt-3 border-t border-line">
        {[1, 2, 3, 4, 5, 6].map((row) => (
          <li
            key={row}
            className="client-row flex flex-col justify-center gap-2 border-b border-line px-4"
          >
            <PlaceholderBar width="w-2/5" />
            <PlaceholderBar width="w-1/4" />
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface ClientListScreenProps {
  view: ClientListView;
  demo: string | null;
}

export function ClientListScreen({ view, demo }: ClientListScreenProps): ReactElement {
  const fallbackDay = view.kind === "list" ? view.fallbackDay : null;
  return (
    <PageFrame strip={fallbackDay ? <FallbackStrip day={fallbackDay} /> : null} demo={demo}>
      <div className="flex flex-col gap-8 wide:gap-12">
        <ClaimBlock />
        <CheckForm off={fallbackDay !== null} />
        <section aria-labelledby="clients-heading">
          <h1 id="clients-heading" className="t-title">
            Clients
          </h1>
          <p className="t-small mt-1 text-ink-3">
            Twelve invented clients on <span className="t-mono">.example</span> domains. Their
            figures are seeded.
          </p>
          {view.kind === "loading" ? (
            <LoadingRows />
          ) : (
            <>
              <WideTable rows={view.rows} />
              <NarrowList rows={view.rows} />
            </>
          )}
        </section>
      </div>
    </PageFrame>
  );
}
