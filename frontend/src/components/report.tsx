// The report as HTML, drawn from the one model in `lib/view/report.ts`: four sections in order,
// the fixes in ink and numbered, then the model's risks in pencil under their marking. Every
// string from the snapshot is rendered as text. No state: it is drawn on the server.

import Link from "next/link";
import type { ReactElement } from "react";
import type {
  ActionsSection,
  AuthenticationSection,
  FiguresSection,
  Report,
  ReportSection,
} from "@/lib/view/report";
import { SeededTag } from "./parts";

function Authentication({ section }: { section: AuthenticationSection }): ReactElement {
  return (
    <div className="sheet mt-3">
      {section.checks.map((check, index) => (
        <div key={check.name} className={`p-4 ${index > 0 ? "border-t border-line" : ""}`}>
          <h3 className="flex flex-wrap items-center gap-2 font-semibold">
            {check.name}
            {check.seeded ? <SeededTag /> : null}
          </h3>
          <p className="mt-1 font-medium text-ink">{check.status}</p>
          {check.notes.map((note) => (
            <p key={note} className="t-small mt-1 text-ink-2">
              {note}
            </p>
          ))}
          {check.records.length > 0 ? (
            <div className="well mt-2">
              <p className="t-small text-ink-2">Records as read</p>
              {check.records.map((record, at) => (
                <p key={`${at}-${record}`} className="t-record text-ink">
                  {record}
                </p>
              ))}
              {check.foundAt ? <p className="t-small mt-1 text-ink-2">{check.foundAt}</p> : null}
            </div>
          ) : (
            <p className="t-small mt-1 text-ink-2">Records as read: none</p>
          )}
        </div>
      ))}
    </div>
  );
}

function Figures({ section }: { section: FiguresSection }): ReactElement {
  return (
    <dl className="mt-3 border-b border-line">
      {section.figures.map((figure) => (
        <div
          key={figure.label}
          className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line py-3"
        >
          <dt className="flex items-center gap-2 text-ink-2">
            {figure.label} {figure.seeded ? <SeededTag /> : null}
          </dt>
          <dd className="text-ink">{figure.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Actions({ section }: { section: ActionsSection }): ReactElement {
  const { advisory } = section;
  return (
    <>
      {/* Fixes first in the document, whatever the model returned. */}
      <h3 className="mt-3 font-semibold text-ink">{section.fixesHeading}</h3>
      <p className="t-small mt-1 text-ink-3">{section.fixesNote}</p>
      <div className="sheet mt-3">
        {section.fixes.length === 0 ? (
          <p className="t-lead measure p-4 text-ink">{section.noFixes}</p>
        ) : (
          <ol>
            {section.fixes.map((fix) => (
              <li key={fix.number} className="fix-item flex gap-3">
                <span className="t-lead font-medium text-ink">{fix.number}.</span>
                <div>
                  <p className="t-lead measure font-medium text-ink">{fix.instruction}</p>
                  <p className="t-small mt-2 flex flex-wrap items-center gap-2 text-ink-3">
                    {fix.source}
                    {fix.seeded ? <SeededTag /> : null}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      <h3 className="mt-8 font-semibold text-ink-2">{advisory.heading}</h3>
      <div className="pencil mt-3">
        <div className="text-ink-2">
          <p className="font-medium">{advisory.mark}</p>
          <p className="measure mt-1">
            {advisory.sentence}{" "}
            <Link href={advisory.evalPath} className="link">
              {advisory.evalLinkText}
            </Link>
          </p>
        </div>
        {advisory.empty ? (
          <div className="text-ink-2">
            {advisory.empty.title ? <p className="font-medium">{advisory.empty.title}</p> : null}
            <p className="measure">{advisory.empty.text}</p>
          </div>
        ) : null}
        {advisory.risks.map((risk, index) => (
          <div key={`${index}-${risk.title}`}>
            <h4 className="t-model-title text-ink-2">{risk.title}</h4>
            <p className="t-model mt-1 text-ink-2">{risk.why}</p>
            <p className="t-small mt-2 text-ink-3">{risk.basedOn}</p>
          </div>
        ))}
        {advisory.handled.length > 0 ? (
          <div className="text-ink-3">
            <p className="t-small font-medium">Handled, so not in the list above</p>
            <ul className="mt-1">
              {advisory.handled.map((item, index) => (
                <li key={`${index}-${item.title}`} className="mt-1">
                  <span className="t-model-title block line-through">{item.title}</span>
                  <span className="t-small block">{item.dates}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </>
  );
}

function Section({ section }: { section: ReportSection }): ReactElement {
  switch (section.kind) {
    case "authentication":
      return <Authentication section={section} />;
    case "reputation":
    case "sending":
      return <Figures section={section} />;
    case "actions":
      return <Actions section={section} />;
  }
}

export interface ReportDocumentProps {
  report: Report;
}

export function ReportDocument({ report }: ReportDocumentProps): ReactElement {
  return (
    <article className="report flex flex-col gap-8">
      <header className="flex flex-col gap-3">
        <h1 className="t-title">{report.title}</h1>
        <dl className="t-small flex flex-col gap-1">
          {report.facts.map((fact) => (
            <div key={fact.label} className="flex gap-2">
              <dt className="shrink-0 whitespace-nowrap text-ink-3">{fact.label}</dt>
              <dd className={fact.mono ? "t-mono text-ink" : "text-ink"}>{fact.value}</dd>
            </div>
          ))}
        </dl>
        {report.notes.map((note) => (
          <p key={note} className="t-small measure text-ink-2">
            {note}
          </p>
        ))}
      </header>
      {report.sections.map((section) => (
        <section key={section.kind} aria-labelledby={`report-${section.kind}`}>
          <h2 id={`report-${section.kind}`} className="t-heading">
            {section.title}
          </h2>
          <Section section={section} />
        </section>
      ))}
    </article>
  );
}
