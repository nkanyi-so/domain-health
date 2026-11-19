# Runtime dependencies

One line of reason per direct runtime dependency. Nothing is added without a line here. Planned at the intake on 2026-11-19; each phase confirms the current version and API before adding, and the lockfiles hold the truth.

## Backend, base set (what the deployed service installs)

| Package | Reason | First used |
|---|---|---|
| `fastapi` | HTTP routes and the OpenAPI schema the frontend types come from. | Phase 0 |
| `pydantic` | One set of models for requests, responses, stored documents and model output; validates model output before use. | Phase 0 |
| `pydantic-settings` | Settings from the environment. | Phase 0 |
| `uvicorn` | Runs the app, locally and in the container. | Phase 0 |
| `dnspython` | DNS TXT lookups with timeouts and typed errors. | Phase 1 |
| `google-cloud-firestore` | The snapshot store and its transactions. | Phase 3 |
| `google-cloud-tasks` | Enqueues one task per client. | Phase 4 |
| `google-auth` | Verifies Google-signed OIDC tokens on the worker. | Phase 4 |
| `httpx` | Posts the change alert to a Slack webhook. | Phase 4 |

## Backend, `live` group (never installed in the deployed image)

| Package | Reason | First used |
|---|---|---|
| `openai` | The live model, for `make eval-live` and `make record` only. | Phase 2 |

## Frontend

| Package | Reason | First used |
|---|---|---|
| `next`, `react`, `react-dom` | The pages and the server routes. | Phase 0 |
| `tailwindcss` | Styling from the design tokens. | Phase 0 |
