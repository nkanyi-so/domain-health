// A client's report: one snapshot, as this visitor sees it, turned into four sections in a fixed
// order (authentication, reputation, sending, actions) and written out as Markdown. The HTML is
// drawn from the same model by `components/report.tsx`. Pure: nothing here fetches or writes.
//
// The product rule holds here as on the page: the rules' fixes are the action list; the model's
// risks come after them, in a part of their own, under the same marking the page uses.

import {
  ADVISORY_HEADING,
  ADVISORY_MARK,
  ADVISORY_SENTENCE,
  ALL_RISKS_HANDLED,
  EVAL_LINK_TEXT,
  EVAL_PATH,
  NO_RISKS_TODAY,
  RISKS_UNAVAILABLE_TITLE,
  RISKS_UNAVAILABLE_WHY,
} from "./advisory";
import { type CheckName, checkRows, fixSource } from "./checks";
import { handledItems } from "./client-page";
import { promptNumber } from "./evals";
import { basedOn } from "./evidence";
import { type Figure, figures } from "./figures";
import { formatDay } from "./format";
import { type ClientPageView, modelOutputFact } from "./screens";

/** A client page that has a snapshot to show: what a report is made from. */
export type SnapshotView = Extract<ClientPageView, { kind: "snapshot" }>;

export interface ReportFact {
  label: string;
  value: string;
  /** Set in monospace: a domain. */
  mono: boolean;
}

export interface ReportCheck {
  name: CheckName;
  /** The answer came from a fixture zone, not from real DNS. */
  seeded: boolean;
  /** "Found, no problems", "Problem found" or "Check not made". */
  status: string;
  notes: string[];
  /** The records as read. Untrusted text: both renderers treat it as text only. */
  records: string[];
  foundAt: string | null;
}

export interface ReportFigure {
  label: string;
  seeded: boolean;
  value: string;
}

export interface ReportFix {
  number: number;
  instruction: string;
  /** "From DNS" or "From seeded figures". */
  source: string;
  seeded: boolean;
}

export interface ReportRisk {
  title: string;
  why: string;
  /** "Based on: the DMARC record, weekly volume" */
  basedOn: string;
}

export interface ReportHandled {
  title: string;
  /** "Handled 20 Nov. Hidden until 20 Dec." */
  dates: string;
}

/** The model's part of the actions section. It always opens with the marking. */
export interface ReportAdvisory {
  heading: string;
  /** "Advisory, unproven." */
  mark: string;
  /** Who picked these and how that did on the evals. */
  sentence: string;
  evalLinkText: string;
  evalPath: string;
  /** The risks this visitor has not handled, in the snapshot's order. */
  risks: ReportRisk[];
  /** What is said in place of a list: none today, all handled, or unavailable. */
  empty: { title: string | null; text: string } | null;
  /** Handled risks: named under the list, never in it. */
  handled: ReportHandled[];
}

export interface AuthenticationSection {
  kind: "authentication";
  title: "Authentication";
  checks: ReportCheck[];
}

export interface FiguresSection {
  kind: "reputation" | "sending";
  title: "Reputation" | "Sending";
  figures: ReportFigure[];
}

export interface ActionsSection {
  kind: "actions";
  title: "Actions";
  fixesHeading: string;
  fixesNote: string;
  fixes: ReportFix[];
  /** What is said when the rules found nothing. */
  noFixes: string;
  advisory: ReportAdvisory;
}

export type ReportSection = AuthenticationSection | FiguresSection | ActionsSection;

export interface Report {
  clientId: string;
  /** The snapshot's day, "2026-11-20". */
  day: string;
  title: string;
  /** Client, domain, snapshot day, prompt version, model output. */
  facts: ReportFact[];
  /** Plain lines under the facts: the client is invented; the data is saved; the day is earlier. */
  notes: string[];
  /** Always these four, in this order. */
  sections: [AuthenticationSection, FiguresSection, FiguresSection, ActionsSection];
}

const REPUTATION_FIGURES = ["Reputation", "Blocklist", "Complaint rate", "Domain age"];
const SENDING_FIGURES = ["Weekly volume", "Bounce rate", "Open rate"];

export const INVENTED_LINE =
  "This client is invented. Its figures and its DNS answers are made up for this demo.";
export const NO_FIXES = "Nothing to fix today. Every rule passed.";

/** What the report says when it is built from the snapshots bundled with the site. */
export function savedDataLine(day: string): string {
  return `From saved data. The live service could not be reached, so this report is built from the snapshot saved with this site on ${formatDay(day)}.`;
}

function pick(all: readonly Figure[], labels: readonly string[], seeded: boolean): ReportFigure[] {
  return labels.flatMap((label) => {
    const figure = all.find((entry) => entry.label === label);
    return figure ? [{ label, seeded, value: figure.value }] : [];
  });
}

function notes(view: SnapshotView): string[] {
  const lines: string[] = [];
  if (view.page.seeded) {
    lines.push(INVENTED_LINE);
  }
  if (view.fallbackDay) {
    lines.push(savedDataLine(view.fallbackDay));
  }
  if (view.shownInsteadOfToday) {
    lines.push(
      `No snapshot for today yet. This report is from the latest one, ${formatDay(view.page.snapshot.day)}.`,
    );
  }
  return lines;
}

function advisory(view: SnapshotView): ReportAdvisory {
  const { snapshot } = view.page;
  const handled = handledItems(view.page).map(({ risk, dates }) => ({ title: risk.title, dates }));
  const unavailable = snapshot.risks_status === "unavailable";
  // `visible` is the list as this visitor sees it: handled risks are already out of it.
  const risks = unavailable
    ? []
    : snapshot.visible.map((risk) => ({
        title: risk.title,
        why: risk.why,
        basedOn: basedOn(risk.evidence),
      }));
  const empty = unavailable
    ? { title: RISKS_UNAVAILABLE_TITLE, text: RISKS_UNAVAILABLE_WHY }
    : risks.length > 0
      ? null
      : { title: null, text: handled.length > 0 ? ALL_RISKS_HANDLED : NO_RISKS_TODAY };
  return {
    heading: ADVISORY_HEADING,
    mark: ADVISORY_MARK,
    sentence: ADVISORY_SENTENCE,
    evalLinkText: EVAL_LINK_TEXT,
    evalPath: EVAL_PATH,
    risks,
    empty,
    handled: unavailable ? [] : handled,
  };
}

/** The report for one snapshot view: the same data the client page draws. */
export function buildReport(view: SnapshotView): Report {
  const { page } = view;
  const { snapshot } = page;
  const all = figures(snapshot.sources);
  return {
    clientId: page.id,
    day: snapshot.day,
    title: `Domain health report: ${page.name}`,
    facts: [
      { label: "Client", value: page.name, mono: false },
      { label: "Domain", value: snapshot.domain, mono: true },
      { label: "Snapshot", value: `${formatDay(snapshot.day)} (UTC)`, mono: false },
      { label: "Prompt version", value: promptNumber(snapshot.prompt_version), mono: false },
      { label: "Model output", value: modelOutputFact(view), mono: false },
    ],
    notes: notes(view),
    sections: [
      {
        kind: "authentication",
        title: "Authentication",
        checks: checkRows(snapshot.checks, snapshot.fixes).map((row) => ({
          name: row.name,
          seeded: page.seeded,
          status: row.words,
          notes: row.notes,
          records: row.records,
          foundAt: row.foundAt,
        })),
      },
      // Every figure a snapshot holds is seeded: only seeded clients have snapshots, and the
      // page tags them the same way.
      { kind: "reputation", title: "Reputation", figures: pick(all, REPUTATION_FIGURES, true) },
      { kind: "sending", title: "Sending", figures: pick(all, SENDING_FIGURES, true) },
      {
        kind: "actions",
        title: "Actions",
        fixesHeading: "Fixes",
        fixesNote: "Found by rules. Each has one correct fix.",
        fixes: snapshot.fixes.map((fix, index) => ({
          number: index + 1,
          instruction: fix.instruction,
          source: fixSource(fix),
          seeded: page.seeded,
        })),
        noFixes: NO_FIXES,
        advisory: advisory(view),
      },
    ],
  };
}

/** "northwind-cycles-2026-11-20.md": only letters, digits and hyphens before the ending. */
export function reportFileName(report: Pick<Report, "clientId" | "day">): string {
  const safe = (text: string): string => text.toLowerCase().replace(/[^a-z0-9-]+/g, "-");
  return `${safe(report.clientId)}-${safe(report.day)}.md`;
}

// ---------------------------------------------------------------------------------------------
// Markdown
// ---------------------------------------------------------------------------------------------

/** Text from the snapshot as plain Markdown text: one line, with nothing left that marks up. */
function plain(text: string): string {
  return text
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[\\`*_[\]<>~]/g, "\\$&")
    .replace(/&(?=[#a-zA-Z])/g, "\\&");
}

/** A record as read, in a code span whose fence is longer than any run of backticks inside. */
function code(text: string): string {
  const flat = text.replace(/[\r\n]+/g, " ");
  if (flat.trim() === "") {
    return "(empty)";
  }
  const longest = Math.max(0, ...(flat.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(longest + 1);
  const pad = flat.startsWith("`") || flat.endsWith("`") ? " " : "";
  return `${fence}${pad}${flat}${pad}${fence}`;
}

function seededWord(seeded: boolean): string {
  return seeded ? " (seeded)" : "";
}

function checkMarkdown(check: ReportCheck): string[] {
  const lines = [`### ${check.name}${seededWord(check.seeded)}`, "", `Status: ${check.status}`, ""];
  if (check.notes.length > 0) {
    lines.push(...check.notes.map((note) => `- ${plain(note)}`), "");
  }
  if (check.records.length === 0) {
    lines.push("Records as read: none", "");
  } else {
    lines.push("Records as read:", "", ...check.records.map((record) => `- ${code(record)}`), "");
    if (check.foundAt) {
      lines.push(plain(check.foundAt), "");
    }
  }
  return lines;
}

function figuresMarkdown(section: FiguresSection): string[] {
  return [
    ...section.figures.map(
      (figure) => `- ${figure.label}${seededWord(figure.seeded)}: ${plain(figure.value)}`,
    ),
    "",
  ];
}

function actionsMarkdown(section: ActionsSection, baseUrl: string): string[] {
  const { advisory: model } = section;
  const lines = [`### ${section.fixesHeading}`, "", section.fixesNote, ""];
  if (section.fixes.length === 0) {
    lines.push(section.noFixes, "");
  } else {
    for (const fix of section.fixes) {
      lines.push(
        `${fix.number}. ${plain(fix.instruction)}`,
        `   - Source: ${fix.source}${seededWord(fix.seeded)}`,
      );
    }
    lines.push("");
  }
  lines.push(
    `### ${model.heading}`,
    "",
    `**${model.mark}** ${model.sentence} [${model.evalLinkText}](${baseUrl}${model.evalPath})`,
    "",
  );
  if (model.empty) {
    const title = model.empty.title ? `${model.empty.title}. ` : "";
    lines.push(`${title}${model.empty.text}`, "");
  }
  if (model.risks.length > 0) {
    for (const risk of model.risks) {
      lines.push(`- **${plain(risk.title)}**: ${plain(risk.why)} ${plain(risk.basedOn)}.`);
    }
    lines.push("");
  }
  if (model.handled.length > 0) {
    lines.push("Handled, so not in the list above:", "");
    lines.push(...model.handled.map((item) => `- ${plain(item.title)}. ${item.dates}`), "");
  }
  return lines;
}

function sectionMarkdown(section: ReportSection, baseUrl: string): string[] {
  const heading = [`## ${section.title}`, ""];
  switch (section.kind) {
    case "authentication":
      return [...heading, ...section.checks.flatMap(checkMarkdown)];
    case "reputation":
    case "sending":
      return [...heading, ...figuresMarkdown(section)];
    case "actions":
      return [...heading, ...actionsMarkdown(section, baseUrl)];
  }
}

export interface MarkdownOptions {
  /** The site's own address ("https://host"), so the eval link works from a saved file. */
  baseUrl?: string;
}

/** The report as Markdown: headings, lists and one link, and no HTML. */
export function reportMarkdown(report: Report, options: MarkdownOptions = {}): string {
  const baseUrl = (options.baseUrl ?? "").replace(/\/+$/, "");
  const lines = [
    `# ${plain(report.title)}`,
    "",
    ...report.facts.map(
      (fact) => `- ${fact.label}: ${fact.mono ? code(fact.value) : plain(fact.value)}`,
    ),
    "",
    ...report.notes.flatMap((note) => [note, ""]),
    ...report.sections.flatMap((section) => sectionMarkdown(section, baseUrl)),
  ];
  return `${lines.join("\n").trimEnd()}\n`;
}
