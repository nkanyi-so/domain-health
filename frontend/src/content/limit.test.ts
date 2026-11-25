import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LIMIT } from "./limit";

// The sentence in docs/EVALS.md starts lower case, inside a longer sentence, and ends at its
// closing bracket.
function limitInSpec(): string[] {
  const text = readFileSync(resolve(__dirname, "../../../docs/EVALS.md"), "utf8");
  const found = [
    ...text.matchAll(/(on this project's evals a table of rules does better[^\n]*?to its none\))/g),
  ];
  return found.map((match) => match[1]);
}

describe("the limit beside the claim", () => {
  it("is the sentence beside the claim in docs/EVALS.md, word for word", () => {
    const inSpec = limitInSpec();
    expect(inSpec).toHaveLength(1);
    expect(LIMIT.charAt(0)).toBe("O");
    expect(LIMIT.charAt(0).toLowerCase() + LIMIT.slice(1) + "").toBe(`${inSpec[0]}.`);
  });

  it("is one sentence", () => {
    expect(LIMIT.endsWith("none).")).toBe(true);
    expect(LIMIT.includes("\n")).toBe(false);
  });
});
