// Small parts used on every screen: chips, the seeded tag, banners and the facts list.

import type { ReactElement, ReactNode } from "react";
import type { AdvisoryChip as AdvisoryChipModel } from "@/lib/view/clients";
import { fixesText } from "@/lib/view/clients";
import { CrossCircle, DashCircle, InfoCircle, TickCircle } from "./icons";

export function SeededTag(): ReactElement {
  return <span className="tag-seeded">seeded</span>;
}

/** "1 fix", "3 fixes" in ink, or "Nothing to fix" in the healthy colours. */
export function FixesChip({ count }: { count: number }): ReactElement {
  return count === 0 ? (
    <span className="chip chip-ok">
      <TickCircle />
      {fixesText(0)}
    </span>
  ) : (
    <span className="chip chip-fixes">{fixesText(count)}</span>
  );
}

/** Always dashed and never filled: the advisory count is the quiet one. */
export function AdvisoryChip({ chip }: { chip: AdvisoryChipModel }): ReactElement {
  if (chip.kind === "unavailable") {
    return (
      <span className="chip chip-muted">
        <DashCircle />
        {chip.text}
      </span>
    );
  }
  return (
    <span className={chip.kind === "count" ? "chip chip-advisory" : "chip chip-muted"}>
      {chip.text}
    </span>
  );
}

export function MetChip({ met }: { met: boolean }): ReactElement {
  return met ? (
    <span className="chip chip-ok">
      <TickCircle />
      met
    </span>
  ) : (
    <span className="chip chip-missed">
      <CrossCircle />
      missed
    </span>
  );
}

export type BannerTone = "notice" | "error" | "ok";

export interface BannerProps {
  tone: BannerTone;
  title: string;
  children?: ReactNode;
  /** `alert` for errors and refusals; a notice is read with the page. */
  role?: "alert" | "status";
  id?: string;
}

export function Banner({ tone, title, children, role, id }: BannerProps): ReactElement {
  return (
    <div id={id} role={role} className={`banner banner-${tone}`}>
      {tone === "notice" ? <InfoCircle /> : tone === "error" ? <CrossCircle /> : <TickCircle />}
      <div className="measure">
        <p className="banner-title">{title}</p>
        {children}
      </div>
    </div>
  );
}

export interface Fact {
  label: string;
  value: string;
}

/** Label and value pairs in small type: one row at the wide breakpoint, stacked on a phone. */
export function Facts({ facts }: { facts: readonly Fact[] }): ReactElement {
  return (
    <dl className="t-small flex flex-col gap-1 wide:flex-row wide:flex-wrap wide:gap-x-8">
      {facts.map((fact) => (
        <div key={fact.label} className="flex gap-2">
          <dt className="text-ink-3">{fact.label}</dt>
          <dd className="text-ink">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A grey bar where text will be. */
export function PlaceholderBar({ width }: { width: "w-2/5" | "w-1/4" | "w-3/5" }): ReactElement {
  return <div className={`placeholder-bar ${width}`} />;
}
