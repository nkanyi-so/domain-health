# 0001: rules for fixes, a model for ranked risks from a closed list

**Status:** accepted, 2026-11-19 (intake)

**Context.** A health check produces two different things. Some faults have one correct fix (no SPF record, more than ten SPF lookups, no DMARC record, a blocklisting, a complaint rate over the provider's hard limit). Others are a judgment about several signals together (a complaint rate drifting toward the limit while volume rises; a DMARC policy left at `none` on a domain with real volume). The model's list also needs IDs that stay the same from day to day, so "handled" means something tomorrow.

**Decision.** Rules produce the fix list; the model never sees a fault as a question. The model ranks up to eight risks, each a type from a closed list of about twelve defined in `evals/RUBRIC.md`, with its own title and reason. Code builds each ID as `<type>:<domain>`, applies suppression and shows the first five. Code validates the output: a known type, no duplicates, at most eight, every number in the text present in the input.

**Consequence.** IDs are stable by construction, not by asking the model to be consistent. Every eval score can be computed in code, with no judge. The cost: the model cannot name a risk outside the list; a new kind of risk is a change to the rubric, the code and the labels, which is the owner's. The model returns eight so that five remain visible after handled risks are hidden; the evals score the first five. Revisit if the rubric's list proves too coarse on the eval cases.
