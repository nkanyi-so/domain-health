# 0002: OpenAI structured outputs, reasoning off; first on `gpt-6-luna`, on `gpt-6.1-terra` since the paid eval runs

**Status:** accepted, 2026-11-19. The one unverified part was settled by the first paid eval call the same day: `temperature` is accepted with reasoning off (see "Settled" at the end).

**Context.** The original brief is "OpenAI structured outputs, low temperature". Checked on 2026-11-19:

- OpenAI's structured-outputs guide: available "in our latest large language models, starting with GPT-4o"; the Python route is `client.responses.parse(..., text_format=<pydantic model>)`; schemas need every field required and `additionalProperties: false`; the app must handle refusals and incomplete responses.
- OpenAI's models and pricing pages: the current family is GPT-6. `gpt-6-luna` costs $0.10 in and $0.50 out per million tokens and lists reasoning effort `none`; `gpt-6.1-terra` costs $1 and $5 and also lists `none`; the larger models do not list `none`.
- Temperature: OpenAI's model pages no longer mention it. Developer reports (issues on the Vercel AI SDK and other client libraries, read through a search summary, not verified on an official page) agree that `temperature` is accepted only when reasoning effort is `none`, and rejected otherwise.

**Decision.** `gpt-6-luna` through the Responses API with a pydantic schema, reasoning effort `none`, `temperature` 0. The first paid call sends exactly that and records whether it is accepted.

- Accepted: the wording "low temperature" stands.
- Rejected: the parameter is removed, the README says "reasoning off, no sampling control; stability is measured, not assumed", and the stability bar carries the point. I approved this wording change in advance.

If Luna misses a bar after up to four prompt versions, `gpt-6.1-terra` is run on the same set and the numbers decide. The model name is configuration, recorded with every result.

**Consequence.** A full eval run of sixty calls costs about three cents. The choice rests on a behaviour not documented officially, so it is tested before anything depends on it. Revisit when the model is retired or the eval scores move on a new snapshot of it.

## Settled by the first paid call, 2026-11-19

The first paid call (`make eval-live PROBE=1`) sent `gpt-6-luna` a request through the Responses API with the structured-output schema, reasoning effort `none` and `temperature` 0, on a seeded client's input that is not an eval case. It was accepted and completed: 766 tokens in, 13 out, $0.000083. So `temperature = 0` stays in `evals/settings.toml` and is sent with every call, and the wording "low temperature" stands. The code still carries the other branch: with the line removed from the settings file the parameter is not sent at all, and a request the API refuses is raised to the caller, never recorded as a dropped output.

The run sizes quoted above are the first estimate: an eval run is now 144 calls (forty-eight cases, three runs each; decision 0010).

## The model is `gpt-6.1-terra`, 2026-11-19

The decision above chose `gpt-6-luna` and said that if it missed a bar after its prompt versions, `gpt-6.1-terra` would be run on the same set and the numbers would decide. They did. On three different prompt versions, at temperature 0 with reasoning off, Luna gave a different list for the same input in a quarter to a third of the forty-eight cases (stability 0.792, 0.667, 0.688 against a bar of 0.90). Terra on the third of those versions, unchanged, gave stability 0.979, coverage 0.896 and precision 0.962. The attempts and their numbers are in [docs/EVALS.md](../EVALS.md).

So `evals/settings.toml` names `gpt-6.1-terra`, and that is the model whose recordings the deployed service replays. I confirmed the choice. Cost: about ten times Luna's, $0.78 for an eval run of 144 calls and a few cents more for the deployed service's recordings; the worst case for the whole build stays under $7 of the $10 cap. Three prompt versions were run on Luna, not the four the decision allowed, because the fault was the model's run-to-run variation and not the prompt's wording. The same prompt version run on a second model is not "an unchanged prompt run again to get a pass": the rule for paid runs now says "on the same model".
