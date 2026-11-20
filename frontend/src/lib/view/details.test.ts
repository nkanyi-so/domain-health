// Evidence words, check rows, figures, the eval page's words and the bundled data's shape.

import { describe, expect, it } from "vitest";
import { DEMO_RESULT } from "@/data/demo-states";
import type { CheckResults } from "../api-types";
import { FALLBACK } from "../fallback";
import { checkRows, fixSource } from "./checks";
import {
  EVAL_SUMMARY,
  type EvalSummary,
  barWords,
  casesFact,
  harmfulWords,
  missedMeasures,
  missedSentence,
  modelScore,
  promptNumber,
  score,
} from "./evals";
import { EVIDENCE_WORDS, basedOn, evidenceWords, unnamedEvidence } from "./evidence";
import { figures } from "./figures";

const pages = Object.values(FALLBACK.snapshots);

describe("the bundled snapshots", () => {
  it("hold the twelve seeded clients, all on .example domains", () => {
    expect(FALLBACK.generated_for_day).toBe(FALLBACK.clients.day);
    expect(FALLBACK.clients.clients).toHaveLength(12);
    expect(Object.keys(FALLBACK.snapshots)).toEqual(FALLBACK.clients.clients.map((c) => c.id));
    for (const page of pages) {
      expect(page.snapshot.domain.endsWith(".example")).toBe(true);
      expect(page.snapshot.day).toBe(FALLBACK.generated_for_day);
      expect(page.snapshot.model_source).toBe("recorded");
      expect(page.handled).toEqual({});
    }
  });
});

describe("what a risk is based on", () => {
  it("has plain words for every evidence field the seeded recordings use", () => {
    const used = pages.flatMap((page) => page.snapshot.ranked.flatMap((risk) => risk.evidence));

    expect(used.length).toBeGreaterThan(20);
    // Any field listed here would show on the page by its own name.
    expect(unnamedEvidence(used)).toEqual([]);
  });

  it("uses the design's words", () => {
    expect(new Set(Object.values(EVIDENCE_WORDS))).toEqual(
      new Set([
        "the SPF record",
        "the DKIM keys",
        "the DMARC record",
        "reputation grade",
        "complaint rate",
        "bounce rate",
        "weekly volume",
        "open rate",
        "blocklist history",
        "domain age",
        "the fix list",
      ]),
    );
  });

  it("says each thing once, in order, and shows an unknown field by its own name", () => {
    expect(
      basedOn([
        "sources.volume_7d",
        "sources.volume_prev_7d",
        "sources.reputation.grade",
        "sources.domain_age_days",
      ]),
    ).toBe("Based on: weekly volume, reputation grade, domain age");
    expect(evidenceWords("sources.something_new")).toBe("sources.something_new");
    expect(unnamedEvidence(["sources.something_new", "fixes", "toString"])).toEqual([
      "sources.something_new",
      "toString",
    ]);
  });
});

describe("what was checked", () => {
  it("reads found, problem and not made", () => {
    const { snapshot } = FALLBACK.snapshots["northwind-cycles"];
    const rows = checkRows(snapshot.checks, snapshot.fixes);

    expect(rows.map((row) => [row.name, row.words])).toEqual([
      ["SPF", "Found, no problems"],
      ["DKIM", "Problem found"],
      ["DMARC", "Problem found"],
    ]);
    expect(rows[0].records).toEqual(["v=spf1 include:_spf.mailbarrow.example ~all"]);
    expect(rows[1].notes).toEqual(["No DKIM key was found at the 12 common selectors probed."]);
    expect(rows[2].notes).toEqual(["No DMARC record was found."]);
  });

  it("keeps a record's own tag in the case it was read in", () => {
    const { snapshot } = FALLBACK.snapshots["fernhollow-garden"];
    const dmarc = checkRows(snapshot.checks, snapshot.fixes)[2];

    expect(dmarc.notes).toEqual(["p=monitor is not one of none, quarantine, reject."]);
  });

  it("marks a check with a fix as a problem even when the check lists none in words", () => {
    for (const page of pages) {
      const rows = checkRows(page.snapshot.checks, page.snapshot.fixes);
      for (const fix of page.snapshot.fixes.filter((entry) => entry.source === "dns")) {
        const name = fix.type.split("_")[0].toUpperCase();
        expect(rows.find((row) => row.name === name)?.state).toBe("problem");
      }
    }
  });

  it("never reads a check that was not made as a missing record", () => {
    const checks: CheckResults = {
      ...DEMO_RESULT.checks,
      dkim: { reason: "the lookup of s2._domainkey.example.com did not answer" },
      dmarc: { reason: "the domain's forty lookups were spent" },
    };
    const rows = checkRows(checks, []);

    expect(rows[1]).toMatchObject({
      state: "not-made",
      words: "Check not made",
      notes: ["The lookup did not answer in time, so nothing is assumed. No fix is listed for it."],
      records: [],
    });
    expect(rows[2].notes).toEqual([
      "The check could not be finished, so nothing is assumed. No fix is listed for it.",
    ]);
  });

  it("names a fix's source", () => {
    expect(fixSource({ type: "spf_missing", source: "dns", instruction: "" })).toBe("From DNS");
    expect(fixSource({ type: "blocklist_listed", source: "seeded", instruction: "" })).toBe(
      "From seeded figures",
    );
  });
});

describe("the figures", () => {
  it("say each value with its previous reading in words", () => {
    const rows = figures({
      reputation: { grade: "medium", previous_grade: "high" },
      complaint_rate_pct: 0.04,
      bounce_rate_pct: 0.8,
      volume_7d: 6200,
      volume_prev_7d: 6000,
      open_rate_pct: 41,
      open_rate_prev_pct: 40,
      blocklist: { listed: false, listings_90d: 0, days_since_delisted: null },
      domain_age_days: 400,
    });

    expect(rows.map((row) => `${row.label}: ${row.value}`)).toEqual([
      "Reputation: medium, was high",
      "Complaint rate: 0.04%",
      "Bounce rate: 0.8%",
      "Weekly volume: 6,200, was 6,000",
      "Open rate: 41%, was 40%",
      "Blocklist: Not listed. 0 listings in 90 days",
      "Domain age: 400 days",
    ]);
  });

  it("leaves out a previous reading that does not exist and says when a listing ended", () => {
    const { sources } = FALLBACK.snapshots["northwind-cycles"].snapshot;
    const rows = figures({
      ...sources,
      blocklist: { listed: false, listings_90d: 1, days_since_delisted: 12 },
    });

    expect(rows[4].value).toBe("38%");
    expect(rows[5].value).toBe("Not listed. 1 listing in 90 days. Delisted 12 days ago");
  });
});

describe("the eval page's words", () => {
  const summary = EVAL_SUMMARY;

  it("reads the bundled summary: totals only, the numbers of evals/results.json", () => {
    expect(summary.case_runs).toBe(summary.cases * summary.runs);
    expect(summary.sets.table.cases + summary.sets.open.cases).toBe(summary.cases);
    expect(JSON.stringify(summary)).not.toMatch(/"(cases|rows|per_case)":\s*\[/);
  });

  it("states the miss the results hold, and never calls every bar met while one is missed", () => {
    const missed = missedMeasures(summary);

    expect(summary.all_bars_met).toBe(missed.length === 0);
    expect(missed).toEqual(["harmful"]);
    expect(missedSentence(summary)).toBe(
      `One bar is missed: harmful. The model returned a risk the label calls wrong ${summary.measures.harmful.value} times in ${summary.case_runs} case-runs.`,
    );
  });

  it("names every missed bar when more than one is missed, and says so when none is", () => {
    const two: EvalSummary = {
      ...summary,
      measures: {
        ...summary.measures,
        harmful: { value: 12, bar: "== 0", met: false },
        stability: { value: 0.8125, bar: ">= 0.9", met: false },
      },
    };
    const none: EvalSummary = {
      ...summary,
      measures: { ...summary.measures, harmful: { value: 0, bar: "== 0", met: true } },
    };

    expect(missedSentence(two)).toBe(
      "Two bars are missed: harmful, stability. The model returned a risk the label calls wrong 12 times in 144 case-runs. Stability scored 0.813 against a bar of at least 0.90.",
    );
    expect(missedSentence(none)).toBe("All four bars are met.");
  });

  it("writes bars and scores as the design does", () => {
    expect(barWords(">= 0.8")).toBe("at least 0.80");
    expect(barWords(">= 0.9")).toBe("at least 0.90");
    expect(barWords("== 0")).toBe("exactly 0");
    expect(score(0.8955223880597015)).toBe("0.896");
    expect(score(1)).toBe("1.000");
    expect(promptNumber("risks-v3")).toBe("3");
    expect(casesFact(summary)).toBe("48, three runs each: 144 case-runs");
  });

  it("writes harmful as a count, and a count of none with how far it goes", () => {
    expect(harmfulWords(9, { cases: 48, runs: 3, stability: 0.979 })).toBe("9 in 144 case-runs");
    expect(harmfulWords(0, { cases: 48, runs: 3, stability: 47 / 48 })).toBe(
      "0 in 144 case-runs (48 cases, 3 runs whose first five agreed on 47)",
    );
    expect(modelScore("harmful", summary)).toBe(
      `${summary.measures.harmful.value} in ${summary.case_runs} case-runs`,
    );
    expect(modelScore("coverage", summary)).toBe(score(summary.measures.coverage.value));
  });
});
