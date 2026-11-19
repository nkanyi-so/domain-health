# 0002: OpenAI structured outputs on `gpt-6-luna`, reasoning off

**Status:** accepted, 2026-11-19 (intake). One part is unverified and Phase 2 settles it.

**Context.** The brief is "OpenAI structured outputs, low temperature". Checked on 2026-11-19:

- OpenAI's structured-outputs guide: available "in our latest large language models, starting with GPT-4o"; the Python route is `client.responses.parse(..., text_format=<pydantic model>)`; schemas need every field required and `additionalProperties: false`; the app must handle refusals and incomplete responses.
- OpenAI's models and pricing pages: the current family is GPT-6. `gpt-6-luna` costs $0.10 in and $0.50 out per million tokens and lists reasoning effort `none`; `gpt-6.1-terra` costs $1 and $5 and also lists `none`; the larger models do not list `none`.
- Temperature: OpenAI's model pages no longer mention it. Developer reports (issues on the Vercel AI SDK and other client libraries, read through a search summary, not verified on an official page) agree that `temperature` is accepted only when reasoning effort is `none`, and rejected otherwise.

**Decision.** `gpt-6-luna` through the Responses API with a pydantic schema, reasoning effort `none`, `temperature` 0. The first paid call in Phase 2 sends exactly that and records whether it is accepted.

- Accepted: the wording "low temperature" stands.
- Rejected: the parameter is removed, the README says "reasoning off, no sampling control; stability is measured, not assumed", and the stability bar carries the point. This is a wording change the owner approved in advance at the intake.

If Luna misses a bar after up to four prompt versions, `gpt-6.1-terra` is run on the same set and the numbers decide. The model name is configuration, recorded with every result.

**Consequence.** A full eval run of sixty calls costs about three cents. The choice rests on a behaviour not documented officially, so it is tested before anything depends on it. Revisit when the model is retired or the eval scores move on a new snapshot of it.
