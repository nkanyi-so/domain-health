# 0002: OpenAI structured outputs on `gpt-6-luna`, reasoning off

**Status:** accepted, 2026-11-19 (intake). The one unverified part was settled in Phase 2 the same day: `temperature` is accepted with reasoning off (see "Settled" at the end).

**Context.** The brief is "OpenAI structured outputs, low temperature". Checked on 2026-11-19:

- OpenAI's structured-outputs guide: available "in our latest large language models, starting with GPT-4o"; the Python route is `client.responses.parse(..., text_format=<pydantic model>)`; schemas need every field required and `additionalProperties: false`; the app must handle refusals and incomplete responses.
- OpenAI's models and pricing pages: the current family is GPT-6. `gpt-6-luna` costs $0.10 in and $0.50 out per million tokens and lists reasoning effort `none`; `gpt-6.1-terra` costs $1 and $5 and also lists `none`; the larger models do not list `none`.
- Temperature: OpenAI's model pages no longer mention it. Developer reports (issues on the Vercel AI SDK and other client libraries, read through a search summary, not verified on an official page) agree that `temperature` is accepted only when reasoning effort is `none`, and rejected otherwise.

**Decision.** `gpt-6-luna` through the Responses API with a pydantic schema, reasoning effort `none`, `temperature` 0. The first paid call in Phase 2 sends exactly that and records whether it is accepted.

- Accepted: the wording "low temperature" stands.
- Rejected: the parameter is removed, the README says "reasoning off, no sampling control; stability is measured, not assumed", and the stability bar carries the point. This is a wording change the owner approved in advance at the intake.

If Luna misses a bar after up to four prompt versions, `gpt-6.1-terra` is run on the same set and the numbers decide. The model name is configuration, recorded with every result.

**Consequence.** A full eval run of sixty calls costs about three cents. The choice rests on a behaviour not documented officially, so it is tested before anything depends on it. Revisit when the model is retired or the eval scores move on a new snapshot of it.

## Settled in Phase 2, 2026-11-19

The first paid call of Phase 2 (`make eval-live PROBE=1`) sent `gpt-6-luna` a request through the Responses API with the structured-output schema, reasoning effort `none` and `temperature` 0, on a seeded client's input that is not an eval case. It was accepted and completed: 766 tokens in, 13 out, $0.000083. So `temperature = 0` stays in `evals/settings.toml` and is sent with every call, and the wording "low temperature" stands. The code still carries the other branch: with the line removed from the settings file the parameter is not sent at all, and a request the API refuses is raised to the caller, never recorded as a dropped output.

The run sizes quoted above are the intake's: an eval run is now 144 calls (forty-eight cases, three runs each; decision 0010).
