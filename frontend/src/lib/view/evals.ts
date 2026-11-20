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

/** One run on the open cases: what the model found and got wrong, beside rules alone. */
export interface OpenRun {
  run: number;
  expected: number;
  found: number;
  harmful: number;
  rules_found: number;
  rules_harmful: number;
}

/** Rules alone over all the cases: the four scores, and whether they meet the four bars. */
export interface RulesOnly {
  coverage: number;
  precision: number;
  harmful: number;
  stability: number;
  all_bars_met: boolean;
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
  open_runs: OpenRun[];
  rules_only: RulesOnly;
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

/**
 * A score to three decimals, as `make eval` prints it: "0.896". A value exactly half way between
 * two of them goes to the even one, as Python's formatting does (0.8125 is "0.812"), where
 * `toFixed` alone would round it up. Only an odd number of sixteenths can be exactly half way.
 */
export function score(value: number): string {
  const sixteenths = value * 16;
  if (Number.isInteger(sixteenths) && sixteenths % 2 !== 0) {
    const below = Math.floor(value * 1000);
    return ((below % 2 === 0 ? below : below + 1) / 1000).toFixed(3);
  }
  return value.toFixed(3);
}

/** Whether a value meets a bar as the summary writes it: ">= 0.8", "== 0". */
export function meetsBar(value: number, bar: string): boolean {
  const match = /^(>=|==|<=)\s*(\d+(?:\.\d+)?)$/.exec(bar.trim());
  if (!match) {
    throw new Error(`a bar this page cannot read: ${bar}`);
  }
  const limit = Number(match[2]);
  return match[1] === ">=" ? value >= limit : match[1] === "<=" ? value <= limit : value === limit;
}

/** The bars a version not in use missed, worked out from its scores and the bars. */
export function notInUseMissed(entry: NotInUse, summary: EvalSummary): MeasureName[] {
  return MEASURES.filter((name) => !meetsBar(entry[name], summary.measures[name].bar));
}

/**
 * "Prompt version 4, the final attempt, missed two bars: harmful and stability." The versions
 * not in use are listed newest last, and the newest was the final attempt (docs/SPEC.md, "The
 * Phase 2 result").
 */
export function notInUseSentence(entry: NotInUse, summary: EvalSummary): string {
  const last = summary.not_in_use[summary.not_in_use.length - 1];
  const name = `Prompt version ${promptNumber(entry.prompt_version)}`;
  const subject = entry === last ? `${name}, the final attempt,` : name;
  const missed = notInUseMissed(entry, summary);
  if (missed.length === 0) {
    return `${subject} met all four bars.`;
  }
  return missed.length === 1
    ? `${subject} missed one bar: ${missed[0]}.`
    : `${subject} missed ${NUMBER_WORDS[missed.length].toLowerCase()} bars: ${missed.join(" and ")}.`;
}

/**
 * What the coverage and precision scores are taken over: "Coverage and precision are over all 48
 * cases, 30 of them labelled by the rules table's own output; on the 18 open cases alone the
 * model's coverage is 0.720."
 */
export function coverageNote(summary: EvalSummary): string {
  const { table, open } = summary.sets;
  return `Coverage and precision are over all ${summary.cases} cases, ${table.cases} of them labelled by the rules table's own output; on the ${open.cases} open cases alone the model's coverage is ${score(open.coverage)}.`;
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
