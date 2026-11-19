# The claim

The one sentence this project has to prove. It is the owner's: a phase does not edit it.

> A daily email-domain health check for many clients: clear-cut fixes from rules, judgment-call risks picked by a model from a closed list and scored against a written rubric, a human handled loop, and an eval harness for the model's list.

`backend/tests/test_claim_wording.py` reads the quoted line above and fails if that exact sentence is missing from `docs/SPEC.md`, or from the README, the page (`frontend/src/content/claim.ts`) or a report template once each exists. That is all it checks: it cannot see a second, different wording placed beside the sentence. The reviewer reads for that.

What stands behind each part, and where the evidence is once the phase that builds it has merged:

| Part of the sentence | Shown by |
|---|---|
| daily, for many clients | one scheduled run leaves a snapshot for each of the twelve seeded clients (Phase 4 gate) |
| clear-cut fixes from rules | the rules engine and its fixture cases (Phase 1 gate) |
| judgment-call risks picked by a model from a closed list and scored against a written rubric | the model behind one interface, its output validated, IDs built in code; the closed list and the rubric in `evals/RUBRIC.md`; the four bars over forty-eight cases (Phase 2 gate), which score the model against the rubric's bands on thirty cases and against eighteen written calls that depart from the bands on the rest. The sentence does not say the model judges where rules cannot: that was tried and not shown (decision 0012). The model is still scored beside a rules-only baseline on the open cases, as evidence with no bar |
| a human handled loop | handled and reopen, kept through a concurrent daily write (Phase 3 gate) |
| an eval harness for the model's list | `evals/RUBRIC.md`, the eval cases, `evals/bars.toml`, `make eval` and `evals/results.json` (Phases 0 and 2) |
