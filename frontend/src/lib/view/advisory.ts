// The words that mark the model's risks, kept in one place so the client page and the report
// cannot drift apart (docs/DESIGN.md, "The product rule, as layout").

export const ADVISORY_HEADING = "Advisory risks";
export const ADVISORY_MARK = "Advisory, unproven.";
export const ADVISORY_SENTENCE =
  "A model picked these from a fixed list of risk types. On this project's evals a table of rules did better than the model, so read them as things to look at, not things to do.";
export const EVAL_LINK_TEXT = "See the eval result";
export const EVAL_PATH = "/evals";

export const RISKS_UNAVAILABLE_TITLE = "Risks unavailable today";
export const RISKS_UNAVAILABLE_WHY =
  "The model's answer did not pass its checks, so it was dropped, not repaired. The fixes do not depend on it.";
export const NO_RISKS_TODAY = "No advisory risks today. The model raised nothing for this client.";
export const ALL_RISKS_HANDLED =
  "Every advisory risk is handled. Each one comes back after thirty days, or when you reopen it.";
