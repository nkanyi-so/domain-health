// The claim's limit, word for word from docs/SPEC.md ("Claim"). It is shown wherever the claim
// is shown. A test reads the spec and fails if the two differ.
export const LIMIT: string =
  "On this project's evals a table of rules does better on the risk list than the model: it meets all four bars over the forty-eight cases and no prompt version did (on the thirty table cases the labels are that table's own output; on the eighteen open cases, in each of the three runs, the model found one more expected risk than the table, 18 of 25 against 17, and returned three wrong ones to its none).";
