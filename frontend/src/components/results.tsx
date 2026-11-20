// The parts a client's page and a live-check result share, so the two read alike: the fix list
// and "What was checked". Plain components with no state: used on the server and in the browser.

import type { ReactElement } from "react";
import type { Fix } from "@/lib/api-types";
import { type CheckRow, fixSource } from "@/lib/view/checks";
import { CrossCircle, DashCircle, TickCircle } from "./icons";
import { FixesChip, PlaceholderBar, SeededTag } from "./parts";

export interface FixesSectionProps {
  fixes: readonly Fix[];
  /** A seeded client's sources carry the seeded tag; a typed domain's do not. */
  seeded: boolean;
  /** What the empty sheet says. */
  empty: string;
}

/** The ink sheet. It never disappears: with no fixes it says so in the same place. */
export function FixesSection({ fixes, seeded, empty }: FixesSectionProps): ReactElement {
  return (
    <section aria-labelledby="fixes-heading" className="wide:col-span-7">
      <h2 id="fixes-heading" className="t-heading flex flex-wrap items-center gap-2">
        Fixes <FixesChip count={fixes.length} />
      </h2>
      <p className="t-small mt-1 text-ink-3">Found by rules. Each has one correct fix.</p>
      <div className="sheet mt-3">
        {fixes.length === 0 ? (
          <p className="t-lead measure p-4 text-ink">{empty}</p>
        ) : (
          <ul>
            {fixes.map((fix) => (
              <li key={fix.type} className="fix-item">
                <p className="t-lead measure font-medium text-ink">{fix.instruction}</p>
                <p className="t-small mt-2 flex flex-wrap items-center gap-2 text-ink-3">
                  {fixSource(fix)}
                  {seeded ? <SeededTag /> : null}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function StatusWords({ row }: { row: CheckRow }): ReactElement {
  const tone = row.state === "ok" ? "text-ok" : row.state === "problem" ? "text-ink" : "text-ink-3";
  return (
    <p className={`flex items-center gap-1 font-medium ${tone}`}>
      {row.state === "ok" ? (
        <TickCircle />
      ) : row.state === "problem" ? (
        <CrossCircle />
      ) : (
        <DashCircle />
      )}
      {row.words}
    </p>
  );
}

/** The problems in plain words, or why the check was not made. */
function StatusNotes({ row }: { row: CheckRow }): ReactElement {
  return (
    <>
      {row.notes.map((note) => (
        <p
          key={note}
          className={`t-small mt-1 ${row.state === "not-made" ? "text-ink-3" : "text-ink-2"}`}
        >
          {note}
        </p>
      ))}
    </>
  );
}

function Records({ row }: { row: CheckRow }): ReactElement | null {
  if (row.records.length === 0) {
    return null;
  }
  return (
    <div className="well">
      {row.records.map((record, index) => (
        <p key={`${index}-${record}`} className="t-record text-ink">
          {record}
        </p>
      ))}
      {row.foundAt ? <p className="t-small mt-1 text-ink-3">{row.foundAt}</p> : null}
    </div>
  );
}

function CheckName({ row, tag }: { row: CheckRow; tag: "seeded" | "live" }): ReactElement {
  return (
    <span className="flex flex-wrap items-center gap-2 font-semibold">
      {row.name}
      {tag === "seeded" ? <SeededTag /> : <span className="chip chip-live">Live DNS</span>}
    </span>
  );
}

export interface ChecksSectionProps {
  rows: readonly CheckRow[];
  /** Seeded clients' answers come from fixture zones; a typed domain's are live. */
  tag: "seeded" | "live";
}

/** "What was checked": a table at the wide breakpoint, a block per check on a phone. */
export function ChecksSection({ rows, tag }: ChecksSectionProps): ReactElement {
  return (
    <section aria-labelledby="checks-heading">
      <h2 id="checks-heading" className="t-heading">
        What was checked
      </h2>
      <table className="sheet mt-3 hidden w-full table-fixed border-separate border-spacing-0 text-left wide:table">
        <thead>
          <tr className="t-small bg-sunk text-ink-2">
            <th scope="col" className="w-1/4 px-4 py-2 font-medium">
              Check
            </th>
            <th scope="col" className="w-1/4 px-4 py-2 font-medium">
              Status
            </th>
            <th scope="col" className="w-1/2 px-4 py-2 font-medium">
              Records as read
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <th scope="row" className="border-t border-line px-4 py-3 align-top font-normal">
                <CheckName row={row} tag={tag} />
              </th>
              <td className="border-t border-line px-4 py-3 align-top">
                <StatusWords row={row} />
                <StatusNotes row={row} />
              </td>
              <td className="border-t border-line px-4 py-3 align-top">
                <Records row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="sheet mt-3 wide:hidden">
        {rows.map((row, index) => (
          <div
            key={row.name}
            className={`flex flex-wrap items-start gap-x-4 gap-y-2 p-4 ${index > 0 ? "border-t border-line" : ""}`}
          >
            <dt>
              <CheckName row={row} tag={tag} />
            </dt>
            <dd>
              <StatusWords row={row} />
            </dd>
            {/* Name and status share the first line; what was wrong goes under both. */}
            {row.notes.length > 0 ? (
              <dd className="w-full">
                <StatusNotes row={row} />
              </dd>
            ) : null}
            {row.records.length > 0 ? (
              <dd className="w-full">
                <Records row={row} />
              </dd>
            ) : null}
          </div>
        ))}
      </dl>
    </section>
  );
}

/** State 10: the three checks, each still being looked up. */
export function ChecksLookingUp(): ReactElement {
  return (
    <section aria-labelledby="checks-heading" aria-busy="true">
      <h2 id="checks-heading" className="t-heading">
        What was checked
      </h2>
      <ul className="sheet mt-3">
        {["SPF", "DKIM", "DMARC"].map((name, index) => (
          <li
            key={name}
            className={`flex flex-col gap-2 p-4 wide:flex-row wide:items-center wide:gap-8 ${index > 0 ? "border-t border-line" : ""}`}
          >
            <span className="font-semibold wide:w-1/4">{name}</span>
            <span className="text-ink-3 wide:w-1/4">Looking up</span>
            <span className="block wide:w-1/2">
              <PlaceholderBar width="w-3/5" />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
