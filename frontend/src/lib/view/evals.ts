// The eval page's words. Every number comes from `frontend/src/data/eval-summary.json`, which
// `make eval-summary` copies out of `evals/results.json`; nothing here holds a score.

import raw from "@/data/eval-summary.json";
import { formatCount } from "./format";

export type MeasureName = "coverage" | "precision" | "harmful" | "stability";

export interface Measure {
  value: number;
  bar: string;
  met: boolean;
}

export interface SetTotals {
  cases: number;
  expected_items: number;
  coverage: number;
  precision: number;
  harmful: number;
  stability: number;
  baseline_coverage: number;
  baseline_precision: number;
  baseline_harmful: number;
}

export interface NotInUse {
  prompt_version: string;
  coverage: number;
  precision: number;
  harmful: number;
  stability: number;
}

export interface EvalSummary {
  prompt_version: string;
  model: string;
  recorded_at: string;
  runs: number;
  cases: number;
  case_runs: number;
  dropped: number;
  all_bars_met: boolean;
  better_than_baseline_on_open: boolean;
  measures: Record<MeasureName, Measure>;
  sets: { table: SetTotals; open: SetTotals };
  not_in_use: NotInUse[];
}

export const EVAL_SUMMARY: EvalSummary = raw;

export const MEASURES: readonly MeasureName[] = ["coverage", "precision", "harmful", "stability"];

const LABELS: Record<MeasureName, string> = {
  coverage: "Coverage",
  precision: "Precision",
  harmful: "Harmful",
  stability: "Stability",
};

const NUMBER_WORDS = ["No", "One", "Two", "Three", "Four"];

export function measureLabel(name: MeasureName): string {
  return LABELS[name];
}

/** "3" from "risks-v3": the number the snapshot facts and the eval page show. */
export function promptNumber(version: string): string {
  const match = /(\d+)$/.exec(version);
  return match ? match[1] : version;
}

/** ">= 0.8" reads "at least 0.80"; "== 0" reads "exactly 0". */
export function barWords(bar: string): string {
  const match = /^(>=|==|<=)\s*(\d+(?:\.\d+)?)$/.exec(bar.trim());
  if (!match) {
    return bar;
  }
  const [, op, number] = match;
  const value = number.includes(".") ? Number(number).toFixed(2) : number;
  return `${op === ">=" ? "at least" : op === "<=" ? "at most" : "exactly"} ${value}`;
}

/** A score to three decimals: "0.896". */
export function score(value: number): string {
  return value.toFixed(3);
}

/**
 * Harmful is a count: "9 in 144 case-runs". A count of none says how far that goes: "0 in 144
 * case-runs (48 cases, 3 runs whose first five agreed on 47)", because runs that agree are not
 * separate evidence.
 */
export function harmfulWords(
  count: number,
  totals: { cases: number; runs: number; stability: number },
): string {
  const caseRuns = totals.cases * totals.runs;
  const base = `${formatCount(count)} in ${formatCount(caseRuns)} case-runs`;
  if (count !== 0) {
    return base;
  }
  const agreed = Math.round(totals.stability * totals.cases);
  return `${base} (${totals.cases} cases, ${totals.runs} runs whose first five agreed on ${agreed})`;
}

export function modelScore(name: MeasureName, summary: EvalSummary): string {
  const { value } = summary.measures[name];
  return name === "harmful"
    ? harmfulWords(value, {
        cases: summary.cases,
        runs: summary.runs,
        stability: summary.measures.stability.value,
      })
    : score(value);
}

export function missedMeasures(summary: EvalSummary): MeasureName[] {
  return MEASURES.filter((name) => !summary.measures[name].met);
}

/**
 * One sentence that names every missed bar: "One bar is missed: harmful. The model returned a
 * risk the label calls wrong 9 times in 144 case-runs."
 */
export function missedSentence(summary: EvalSummary): string {
  const missed = missedMeasures(summary);
  if (missed.length === 0) {
    return "All four bars are met.";
  }
  const head =
    missed.length === 1
      ? `One bar is missed: ${missed[0]}.`
      : `${NUMBER_WORDS[missed.length]} bars are missed: ${missed.join(", ")}.`;
  const details = missed.map((name) => {
    const { value, bar } = summary.measures[name];
    if (name === "harmful") {
      const times = value === 1 ? "once" : `${formatCount(value)} times`;
      return `The model returned a risk the label calls wrong ${times} in ${formatCount(summary.case_runs)} case-runs.`;
    }
    return `${LABELS[name]} scored ${score(value)} against a bar of ${barWords(bar)}.`;
  });
  return [head, ...details].join(" ");
}

/** "48, three runs each: 144 case-runs" */
export function casesFact(summary: EvalSummary): string {
  const runs = (NUMBER_WORDS[summary.runs] ?? String(summary.runs)).toLowerCase();
  return `${summary.cases}, ${runs} runs each: ${formatCount(summary.case_runs)} case-runs`;
}
