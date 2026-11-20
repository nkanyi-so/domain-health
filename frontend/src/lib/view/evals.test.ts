import { describe, expect, it } from "vitest";
import {
  EVAL_SUMMARY,
  type EvalSummary,
  coverageNote,
  meetsBar,
  notInUseMissed,
  notInUseSentence,
  score,
} from "./evals";

describe("a score on the eval page", () => {
  it("prints as `make eval` prints it: a value exactly half way goes to the even side", () => {
    expect(score(0.8125)).toBe("0.812");
    expect(score(0.9375)).toBe("0.938");
    expect(score(0.0625)).toBe("0.062");
    expect(score(0.1875)).toBe("0.188");
  });

  it("is otherwise the nearest three decimals", () => {
    expect(score(0.8955223880597015)).toBe("0.896");
    expect(score(0.7200000000000001)).toBe("0.720");
    expect(score(0.9621835443037975)).toBe("0.962");
    expect(score(0.5)).toBe("0.500");
    expect(score(1)).toBe("1.000");
    expect(score(0)).toBe("0.000");
  });

  it("shows every version not in use as the spec's figures have it", () => {
    expect(EVAL_SUMMARY.not_in_use.map((entry) => score(entry.stability))).toEqual(["0.812"]);
  });
});

describe("a bar", () => {
  it("is met or missed as the summary writes it", () => {
    expect(meetsBar(0.8, ">= 0.8")).toBe(true);
    expect(meetsBar(0.79, ">= 0.8")).toBe(false);
    expect(meetsBar(0, "== 0")).toBe(true);
    expect(meetsBar(1, "== 0")).toBe(false);
    expect(() => meetsBar(1, "about 1")).toThrow();
  });

  it("agrees with the results file on the version in use", () => {
    for (const measure of Object.values(EVAL_SUMMARY.measures)) {
      expect(meetsBar(measure.value, measure.bar)).toBe(measure.met);
    }
  });
});

describe("the versions not in use", () => {
  it("names the bars the final attempt missed, from its scores and the bars", () => {
    const [entry] = EVAL_SUMMARY.not_in_use;

    expect(EVAL_SUMMARY.not_in_use).toHaveLength(1);
    expect(notInUseMissed(entry, EVAL_SUMMARY)).toEqual(["harmful", "stability"]);
    expect(notInUseSentence(entry, EVAL_SUMMARY)).toBe(
      "Prompt version 4, the final attempt, missed two bars: harmful and stability.",
    );
  });

  it("follows the scores, not a typed list", () => {
    const [entry] = EVAL_SUMMARY.not_in_use;
    const steady = { ...entry, stability: 0.95 };
    const changed: EvalSummary = { ...EVAL_SUMMARY, not_in_use: [steady] };

    expect(notInUseSentence(steady, changed)).toBe(
      "Prompt version 4, the final attempt, missed one bar: harmful.",
    );
  });
});

describe("the sentence under the bars", () => {
  it("takes its numbers from the summary", () => {
    expect(coverageNote(EVAL_SUMMARY)).toBe(
      "Coverage and precision are over all 48 cases, 30 of them labelled by the rules table's own output; on the 18 open cases alone the model's coverage is 0.720.",
    );
    const { table, open } = EVAL_SUMMARY.sets;
    expect(table.cases + open.cases).toBe(EVAL_SUMMARY.cases);
    expect(table.baseline_coverage).toBe(1);
    expect(table.baseline_precision).toBe(1);
  });
});
