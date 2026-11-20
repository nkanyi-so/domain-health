import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { demoClientPage } from "@/data/demo-states";
import type { ClientPage } from "@/lib/api-types";
import { FALLBACK } from "@/lib/fallback";
import { afterClick } from "@/lib/view/client-page";
import { type SnapshotView, buildReport } from "@/lib/view/report";
import { snapshotView } from "@/lib/view/screens";
import { ReportDocument } from "./report";

function viewOf(page: ClientPage): SnapshotView {
  const view = snapshotView(page, { writes: "on" });
  if (view.kind !== "snapshot") {
    throw new Error("not a snapshot");
  }
  return view;
}

function html(view: SnapshotView): string {
  return renderToStaticMarkup(<ReportDocument report={buildReport(view)} />);
}

const BOTH: ClientPage = FALLBACK.snapshots["northwind-cycles"];

describe("the report as HTML", () => {
  const page = html(viewOf(BOTH));

  it("is one title and the four sections, in order", () => {
    expect(page.match(/<h1/g)).toHaveLength(1);
    expect([...page.matchAll(/<h2[^>]*>([^<]+)<\/h2>/g)].map((match) => match[1])).toEqual([
      "Authentication",
      "Reputation",
      "Sending",
      "Actions",
    ]);
  });

  it("carries the header and the line saying the client is invented", () => {
    expect(page).toContain("Domain health report: Northwind Cycles");
    expect(page).toContain("northwind-cycles.example");
    expect(page).toContain("4 Jan 2026 (UTC)");
    expect(page).toContain("Recorded from a real model run, not generated on this visit");
    expect(page).toContain(
      "This client is invented. Its figures and its DNS answers are made up for this demo.",
    );
  });

  it("tags every seeded figure, check and fix", () => {
    // Three checks, seven figures, two fixes.
    expect(page.match(/class="tag-seeded"/g)).toHaveLength(12);
  });

  it("puts every fix before the advisory risks, and the marking before the first risk", () => {
    const lastFix = page.indexOf("Publish a DMARC record");
    const mark = page.indexOf("Advisory, unproven.");
    const link = page.indexOf('<a class="link" href="/evals">See the eval result</a>');
    const firstRisk = page.indexOf("Sending volume has spiked");

    expect(page.indexOf("Publish a DKIM key")).toBeGreaterThan(-1);
    expect(lastFix).toBeGreaterThan(page.indexOf("Publish a DKIM key"));
    expect(mark).toBeGreaterThan(lastFix);
    expect(page).toContain("On this project&#x27;s evals a table of rules did better");
    expect(link).toBeGreaterThan(mark);
    expect(firstRisk).toBeGreaterThan(link);
  });

  it("keeps a handled risk out of the list, struck through under it", () => {
    const [first] = BOTH.snapshot.ranked;
    const clicked = afterClick(BOTH, first.id, "handled", new Date("2026-01-04T09:00:00Z"));
    const text = html(viewOf(clicked));

    expect(text).not.toContain(`<h4 class="t-model-title text-ink-2">${first.title}</h4>`);
    expect(text.indexOf(first.title)).toBeGreaterThan(text.indexOf("Handled, so not in the list"));
  });

  it("does not say the output was recorded when the risks are unavailable", () => {
    const view = demoClientPage("risks-unavailable");
    if (view.kind !== "snapshot") {
      throw new Error("not a snapshot");
    }
    const text = html(view);
    expect(text).not.toMatch(/recorded from a real model run/i);
    expect(text).toContain("Risks unavailable today");
    expect(text).toContain("Advisory, unproven.");
  });

  it("escapes text from the snapshot", () => {
    const hostile = structuredClone(BOTH);
    const { snapshot } = hostile;
    if ("reason" in snapshot.checks.spf) {
      throw new Error("the SPF check was not made");
    }
    snapshot.checks.spf.records = ['v=spf1 <script>alert("x")</script> ~all'];
    snapshot.fixes[0].instruction = "Publish <b>a key</b>.";
    snapshot.visible[0].title = "<img src=x onerror=alert(1)>";
    const text = html(viewOf(hostile));

    expect(text).not.toContain("<script");
    expect(text).not.toContain("<img");
    expect(text).not.toContain("<b>");
    expect(text).toContain("v=spf1 &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; ~all");
    expect(text).toContain("Publish &lt;b&gt;a key&lt;/b&gt;.");
    expect(text).toContain("&lt;img src=x onerror=alert(1)&gt;");
  });
});
