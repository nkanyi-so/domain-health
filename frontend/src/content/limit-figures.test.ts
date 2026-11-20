// The limit sentence is prose with figures in it. Each figure is held here to the eval summary
// (`src/data/eval-summary.json`, written by `make eval-summary` from the results), so the
// sentence cannot stay as it is while the tables beside it change.

import { describe, expect, it } from "vitest";
import { EVAL_SUMMARY, MEASURES, meetsBar, notInUseMissed } from "@/lib/view/evals";
import { LIMIT } from "./limit";

const ONES = [
  "none",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
  "thirteen",
  "fourteen",
  "fifteen",
  "sixteen",
  "seventeen",
  "eighteen",
  "nineteen",
];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

/** A count under a hundred as the sentence writes it: "forty-eight", "none". */
function words(count: number): string {
  if (!Number.isInteger(count) || count < 0 || count > 99) {
    throw new Error(`no words here for ${count}`);
  }
  if (count < 20) {
    return ONES[count];
  }
  const tens = TENS[Math.floor(count / 10)];
  return count % 10 === 0 ? tens : `${tens}-${ONES[count % 10]}`;
}

/** The one value every run has, or a failure if the runs differ. */
function everyRun(values: number[]): number {
  expect(new Set(values).size).toBe(1);
  return values[0];
}

describe("the limit sentence's figures", () => {
  const summary = EVAL_SUMMARY;
  const { table, open } = summary.sets;
  const runs = summary.open_runs;

  it("counts the cases, the two sets and the runs as the summary does", () => {
    expect(LIMIT).toContain(`over the ${words(summary.cases)} cases`);
    expect(LIMIT).toContain(`on the ${words(table.cases)} table cases`);
    expect(LIMIT).toContain(`on the ${words(open.cases)} open cases`);
    expect(LIMIT).toContain(`in each of the ${words(summary.runs)} runs`);
    expect(table.cases + open.cases).toBe(summary.cases);
    expect(runs.map((run) => run.run)).toEqual(
      Array.from({ length: summary.runs }, (_, index) => index + 1),
    );
  });

  it("says what the model and the table found on the open cases, in each run", () => {
    const expected = everyRun(runs.map((run) => run.expected));
    const found = everyRun(runs.map((run) => run.found));
    const rulesFound = everyRun(runs.map((run) => run.rules_found));

    expect(expected).toBe(open.expected_items);
    expect(LIMIT).toContain(
      `the model found ${words(found - rulesFound)} more expected risk than the table, ${found} of ${expected} against ${rulesFound}`,
    );
    expect(found / expected).toBeCloseTo(open.coverage, 10);
    expect(rulesFound / expected).toBeCloseTo(open.baseline_coverage, 10);
  });

  it("says how many wrong ones each returned on the open cases, in each run", () => {
    const harmful = everyRun(runs.map((run) => run.harmful));
    const rulesHarmful = everyRun(runs.map((run) => run.rules_harmful));

    expect(LIMIT).toContain(`returned ${words(harmful)} wrong ones to its ${words(rulesHarmful)}`);
    expect(harmful * summary.runs).toBe(open.harmful);
    expect(rulesHarmful).toBe(open.baseline_harmful);
  });

  it("says the table meets all four bars, and no prompt version in the summary did", () => {
    expect(LIMIT).toContain("it meets all four bars");
    expect(LIMIT).toContain("no prompt version did");
    expect(MEASURES).toHaveLength(4);
    expect(summary.rules_only.all_bars_met).toBe(true);
    for (const name of MEASURES) {
      expect(meetsBar(summary.rules_only[name], summary.measures[name].bar)).toBe(true);
    }
    expect(summary.all_bars_met).toBe(false);
    expect(MEASURES.some((name) => !summary.measures[name].met)).toBe(true);
    for (const entry of summary.not_in_use) {
      expect(notInUseMissed(entry, summary).length).toBeGreaterThan(0);
    }
  });

  it("says the table cases are labelled by the table's own output", () => {
    expect(LIMIT).toContain("on the thirty table cases the labels are that table's own output");
    expect(table.baseline_coverage).toBe(1);
    expect(table.baseline_precision).toBe(1);
    expect(table.baseline_harmful).toBe(0);
  });
});
