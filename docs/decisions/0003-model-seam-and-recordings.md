# 0003: one model interface; recorded output on the hosted demo; no model call for a typed domain

**Status:** accepted by the owner, 2026-11-19 (intake)

**Context.** The hosted demo must load months later with no key on the visitor's side. A model key in production is the one thing on the site that can run out of credit, be billed or be abused. A domain a visitor types has no reputation, blocklist or sending data, so a model would be judging from DNS alone, which the rules already cover.

**Decision.** The model sits behind `RiskModel` with three implementations: live (OpenAI), recorded (replays committed recordings, looked up by a hash of prompt version, model and input) and fixture (scripted, for tests). The deployed worker is built with the recorded one only. `make record` runs the live model once over every state of every seeded client and commits the output. A typed domain gets real DNS checks and the fix list; the risks panel says it needs data this domain does not have. The `openai` package is in a dependency group the production image does not install.

**Consequence.** The hosted demo cannot spend on a model and has no key to leak. The page and the README say the seeded clients' risks are recorded, with the prompt version and date. The cost: a seeded state with no recording has no risks, so a test fails if any is missing, and a prompt change means recording again. The live model is still exercised for real by the eval run. Revisit if the owner wants a live model call on the hosted page; it would then need its own cap and a funded key.
