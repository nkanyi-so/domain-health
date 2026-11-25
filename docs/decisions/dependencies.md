# Runtime dependencies

One line of reason per direct runtime dependency. Nothing is added without a line here. Planned on 2026-11-19; the current version and API are confirmed before each is added, and the lockfiles hold the truth.

## Backend, base set (what the deployed service installs)

| Package | Reason |
|---|---|
| `fastapi` | HTTP routes and the OpenAPI schema the frontend types come from. |
| `pydantic` | One set of models for requests, responses, stored documents and model output; validates model output before use. |
| `pydantic-settings` | Settings from the environment. |
| `uvicorn` | Runs the app, locally and in the container. |
| `dnspython` | DNS TXT lookups with timeouts and typed errors. |
| `google-cloud-firestore` | The snapshot store and its transactions. |
| `google-cloud-tasks` | Enqueues one task per client. |
| `google-auth` | Verifies Google-signed OIDC tokens on the worker. |
| `httpx2` | Posts the change alert to a Slack webhook and fetches Google's signing certificates. It is `httpx2`, not `httpx`: the installed Starlette's test client already uses it, so the project has one HTTP client and not two. |

## Backend, `live` group (never installed in the deployed image)

| Package | Reason |
|---|---|
| `openai` | The live model, for `make eval-live` and `make record` only. |

## Frontend

| Package | Reason |
|---|---|
| `next`, `react`, `react-dom` | The pages and the server routes. |
| `tailwindcss` | Styling from the design tokens. |
| `playwright-core` (development only, pinned to 1.65.1) | Drives a browser for `make screens`: the 68 screenshots and their contrast, sideways-scroll and focus checks. Not in the deployed build, not used by `make check` or CI. The version is the one whose Chromium build (revision 1255) is already in Playwright's cache, so nothing is downloaded. |
