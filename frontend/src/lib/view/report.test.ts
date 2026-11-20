import { describe, expect, it } from "vitest";
import { demoClientPage } from "@/data/demo-states";
import type { ClientPage } from "../api-types";
import { FALLBACK } from "../fallback";
import { ADVISORY_MARK, ADVISORY_SENTENCE } from "./advisory";
import { afterClick } from "./client-page";
import {
  INVENTED_LINE,
  type Report,
  type SnapshotView,
  buildReport,
  reportFileName,
  reportMarkdown,
} from "./report";
import { snapshotView } from "./screens";

function viewOf(page: ClientPage, rest: { fallbackDay?: string } = {}): SnapshotView {
  const view = snapshotView(page, { writes: "on", ...rest });
  if (view.kind !== "snapshot") {
    throw new Error("not a snapshot");
  }
  return view;
}

function demo(name: "risks-unavailable" | "all-handled" | "healthy"): SnapshotView {
  const view = demoClientPage(name);
  if (view.kind !== "snapshot") {
    throw new Error("not a snapshot");
  }
  return view;
}

/** Fixes and risks both: two of each. */
const BOTH: ClientPage = FALLBACK.snapshots["northwind-cycles"];

/** The same page with something a browser would run in a record, a fix and a risk. */
function hostile(): ClientPage {
  const page = structuredClone(BOTH);
  const { snapshot } = page;
  if ("reason" in snapshot.checks.spf) {
    throw new Error("the SPF check was not made");
  }
  snapshot.checks.spf.records = ["v=spf1 <script>alert(1)</script> `x` ~all"];
  snapshot.fixes[0].instruction = "Publish <b>a key</b> for [this](http://x.example) domain.";
  snapshot.visible[0].title = "<img src=x onerror=alert(1)> *spiked*";
  snapshot.ranked[0].title = snapshot.visible[0].title;
  return page;
}

/** The Markdown with its code spans taken out: what is left is text a reader's tool marks up. */
function outsideCode(markdown: string): string {
  return markdown.replace(/(`+)[^\n]*?\1/g, "");
}

describe("the report model", () => {
  const report: Report = buildReport(viewOf(BOTH));

  it("has the four sections, in order", () => {
    expect(report.sections.map((section) => section.title)).toEqual([
      "Authentication",
      "Reputation",
      "Sending",
      "Actions",
    ]);
  });

  it("carries the client, the domain, the day, the prompt version and where the model output came from", () => {
    expect(report.facts.map((fact) => `${fact.label}: ${fact.value}`)).toEqual([
      "Client: Northwind Cycles",
      "Domain: northwind-cycles.example",
      "Snapshot: 4 Jan 2026 (UTC)",
      "Prompt version: 3",
      "Model output: Recorded from a real model run, not generated on this visit",
    ]);
    expect(report.notes).toEqual([INVENTED_LINE]);
  });

  it("reads SPF, DKIM and DMARC with their status, problems and records", () => {
    const [authentication] = report.sections;
    expect(authentication.checks.map((check) => `${check.name}: ${check.status}`)).toEqual([
      "SPF: Found, no problems",
      "DKIM: Problem found",
      "DMARC: Problem found",
    ]);
    expect(authentication.checks[0].records).toEqual([
      "v=spf1 include:_spf.mailbarrow.example ~all",
    ]);
    expect(authentication.checks[2].notes).toEqual(["No DMARC record was found."]);
    expect(authentication.checks.every((check) => check.seeded)).toBe(true);
  });

  it("puts each figure in its section and labels every one seeded", () => {
    const [, reputation, sending] = report.sections;
    expect(reputation.figures.map((figure) => figure.label)).toEqual([
      "Reputation",
      "Blocklist",
      "Complaint rate",
      "Domain age",
    ]);
    expect(sending.figures.map((figure) => figure.label)).toEqual([
      "Weekly volume",
      "Bounce rate",
      "Open rate",
    ]);
    expect([...reputation.figures, ...sending.figures].every((figure) => figure.seeded)).toBe(true);
    expect(sending.figures[0].value).toMatch(/, was /);
  });

  it("numbers the fixes from the rules, each with its source", () => {
    const actions = report.sections[3];
    expect(actions.fixes.map((fix) => fix.number)).toEqual([1, 2]);
    expect(actions.fixes.map((fix) => fix.instruction)).toEqual(
      BOTH.snapshot.fixes.map((fix) => fix.instruction),
    );
    expect(actions.fixes.every((fix) => fix.source === "From DNS" && fix.seeded)).toBe(true);
  });

  it("lists the risks under the page's own marking", () => {
    const { advisory } = report.sections[3];
    expect(advisory.risks.map((risk) => risk.title)).toEqual(
      BOTH.snapshot.visible.map((risk) => risk.title),
    );
    expect(advisory.mark).toBe("Advisory, unproven.");
    expect(advisory.sentence).toContain("On this project's evals a table of rules did better");
    expect(advisory.evalPath).toBe("/evals");
    expect(advisory.empty).toBeNull();
  });

  it("leaves a handled risk out of the advisory list and names it as handled", () => {
    const [first, second] = BOTH.snapshot.ranked;
    const clicked = afterClick(BOTH, first.id, "handled", new Date("2026-01-04T09:00:00Z"));
    const { advisory } = buildReport(viewOf(clicked)).sections[3];

    expect(advisory.risks.map((risk) => risk.title)).toEqual([second.title]);
    expect(advisory.handled).toEqual([
      { title: first.title, dates: "Handled 4 Jan. Hidden until 3 Feb." },
    ]);
  });

  it("says so when every risk is handled, and when there are none", () => {
    expect(buildReport(demo("all-handled")).sections[3].advisory).toMatchObject({
      risks: [],
      empty: { title: null, text: expect.stringContaining("Every advisory risk is handled.") },
    });
    const healthy = buildReport(demo("healthy")).sections[3];
    expect(healthy.fixes).toEqual([]);
    expect(healthy.advisory.empty?.text).toContain("No advisory risks today.");
  });

  it("never says the output was recorded from a model run when the risks are unavailable", () => {
    const unavailable = buildReport(demo("risks-unavailable"));
    const { advisory } = unavailable.sections[3];

    expect(unavailable.facts.at(-1)).toMatchObject({
      label: "Model output",
      value: "Dropped: it did not pass its checks",
    });
    expect(advisory.risks).toEqual([]);
    expect(advisory.empty?.title).toBe("Risks unavailable today");
    expect(JSON.stringify(unavailable)).not.toMatch(/recorded from a real model run/i);
    expect(reportMarkdown(unavailable)).not.toMatch(/recorded from a real model run/i);
    // The fixes do not depend on the model.
    expect(unavailable.sections[3].fixes.length).toBeGreaterThan(0);
  });

  it("says it is from saved data when the bundled snapshot is what it was built from", () => {
    const saved = buildReport(viewOf(BOTH, { fallbackDay: FALLBACK.generated_for_day }));
    expect(saved.notes).toEqual([
      INVENTED_LINE,
      "From saved data. The live service could not be reached, so this report is built from the snapshot saved with this site on 4 Jan 2026.",
    ]);
    expect(reportMarkdown(saved)).toContain("From saved data.");
    expect(reportMarkdown(report)).not.toContain("From saved data.");
  });

  it("names its file after the client and the day", () => {
    expect(reportFileName(report)).toBe("northwind-cycles-2026-01-04.md");
    expect(reportFileName({ clientId: 'a"b/../c', day: "2026-01-04" })).toBe("a-b-c-2026-01-04.md");
  });
});

describe("the report as Markdown", () => {
  const markdown = reportMarkdown(buildReport(viewOf(BOTH)), { baseUrl: "https://site.example/" });
  const lines = markdown.split("\n");

  it("is one title, then the four sections in order", () => {
    expect(lines[0]).toBe("# Domain health report: Northwind Cycles");
    expect(lines.filter((line) => line.startsWith("# "))).toHaveLength(1);
    expect(lines.filter((line) => line.startsWith("## "))).toEqual([
      "## Authentication",
      "## Reputation",
      "## Sending",
      "## Actions",
    ]);
    expect(lines.filter((line) => line.startsWith("### "))).toEqual([
      "### SPF (seeded)",
      "### DKIM (seeded)",
      "### DMARC (seeded)",
      "### Fixes",
      "### Advisory risks",
    ]);
  });

  it("is well formed: a blank line around every heading, lists that are lists, one ending", () => {
    lines.forEach((line, index) => {
      if (/^#{1,3} /.test(line)) {
        expect(index === 0 ? "" : lines[index - 1]).toBe("");
        expect(lines[index + 1]).toBe("");
      }
      // Every line is a heading, a list item, a paragraph or blank: nothing is indented by
      // accident into a code block.
      expect(line).toMatch(/^(#{1,3} \S|- \S|\d+\. \S| {3}- \S|[A-Z*]|$)/);
    });
    expect(markdown.endsWith("\n")).toBe(true);
    expect(markdown).not.toMatch(/\n\n\n/);
  });

  it("puts the header in a list, with the line saying the client is invented", () => {
    expect(markdown).toContain("- Domain: `northwind-cycles.example`");
    expect(markdown).toContain("- Snapshot: 4 Jan 2026 (UTC)");
    expect(markdown).toContain("- Prompt version: 3");
    expect(markdown).toContain(
      "- Model output: Recorded from a real model run, not generated on this visit",
    );
    expect(markdown).toContain(INVENTED_LINE);
  });

  it("labels every seeded figure and every fix's source", () => {
    for (const label of [
      "Reputation",
      "Blocklist",
      "Complaint rate",
      "Domain age",
      "Weekly volume",
      "Bounce rate",
      "Open rate",
    ]) {
      expect(markdown).toContain(`- ${label} (seeded): `);
    }
    expect(markdown).toContain("   - Source: From DNS (seeded)");
  });

  it("numbers the fixes and puts every one of them before the advisory risks", () => {
    const firstFix = markdown.indexOf("1. Publish a DKIM key");
    const secondFix = markdown.indexOf("2. Publish a DMARC record");
    const advisory = markdown.indexOf("### Advisory risks");
    const firstRisk = markdown.indexOf("- **Sending volume has spiked**");

    expect(firstFix).toBeGreaterThan(markdown.indexOf("### Fixes"));
    expect(secondFix).toBeGreaterThan(firstFix);
    expect(advisory).toBeGreaterThan(secondFix);
    expect(firstRisk).toBeGreaterThan(advisory);
  });

  it("marks the risks advisory and unproven, with the eval result, before the first risk", () => {
    const marking = `**${ADVISORY_MARK}** ${ADVISORY_SENTENCE} [See the eval result](https://site.example/evals)`;
    expect(markdown).toContain(marking);
    expect(markdown.indexOf(marking)).toBeLessThan(markdown.indexOf("- **Sending volume"));
    // Without the site's address the link is the path.
    expect(reportMarkdown(buildReport(viewOf(BOTH)))).toContain("[See the eval result](/evals)");
  });

  it("carries the marking in every state, risks or not", () => {
    for (const name of ["risks-unavailable", "all-handled", "healthy"] as const) {
      const text = reportMarkdown(buildReport(demo(name)));
      expect(text).toContain("**Advisory, unproven.**");
      expect(text).toContain("[See the eval result](/evals)");
      expect(text.indexOf("### Fixes")).toBeLessThan(text.indexOf("### Advisory risks"));
    }
  });

  it("contains no HTML", () => {
    expect(markdown).not.toMatch(/[<>]/);
  });

  it("keeps a record as it was read, in a code span it cannot close", () => {
    const text = reportMarkdown(buildReport(viewOf(hostile())));
    expect(text).toContain("- ``v=spf1 <script>alert(1)</script> `x` ~all``");
    // Outside the code spans no tag, link or emphasis from the snapshot is left standing.
    const rest = outsideCode(text);
    expect(rest).not.toMatch(/(?<!\\)[<>]/);
    expect(rest).toContain("Publish \\<b\\>a key\\</b\\> for \\[this\\](http://x.example) domain.");
    expect(rest).toContain("- **\\<img src=x onerror=alert(1)\\> \\*spiked\\***");
  });
});
