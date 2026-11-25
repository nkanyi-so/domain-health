import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CLAIM } from "./claim";

function claimInDocs(): string[] {
  const text = readFileSync(resolve(__dirname, "../../../docs/EVALS.md"), "utf8");
  return [...text.matchAll(/^> (.+)$/gm)].map((match) => match[1].trim());
}

describe("the claim on the page", () => {
  it("is the one quoted line in docs/EVALS.md", () => {
    expect(claimInDocs()).toEqual([CLAIM]);
  });
});
