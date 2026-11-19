# Architecture: domain-health

## Shape

```
                         Vercel (frontend/)                         Google Cloud (backend/)
visitor ── browser ──> Next.js pages + server routes ── proxy secret ──> Cloud Run: FastAPI
                         │  session cookie (sandbox or admin)              │  /api/*        public API (proxy secret)
                         │  bundled fallback snapshots                     │  /internal/*   dispatch, worker (Google OIDC)
                         └─ if the backend is down: fallback + notice      │
                                                                           ├─ Firestore (snapshots, handled, sandboxes, counters)
Cloud Scheduler ── OIDC ──> /internal/dispatch ──> Cloud Tasks ── OIDC ──> /internal/worker/{client}
```

The backend is a pipeline of pure steps with every outside system behind one interface:

```
resolver ─> checks ─┐
seeded sources ─────┼─> rules ─> fixes ─────────────┐
                    └─> risk model ─> validate ─> ranked risks ─> store (transaction) ─> snapshot
```

| Outside system | Interface | Implementations |
|---|---|---|
| DNS | `Resolver` (`txt(name)` returns records, no-such-name or timeout) | `LiveResolver` (real DNS), `FixtureResolver` (zone data in `backend/fixtures/zones/`) |
| Language model | `RiskModel` (`rank(snapshot_input)` returns a validated ranked list) | `OpenAIRiskModel` (live; only `make eval-live` and `make record` build it), `RecordedRiskModel` (replays committed recordings by input hash; the deployed worker and `make eval` use it), `FixtureRiskModel` (scripted; tests) |
| Database | `SnapshotStore` (read snapshot, write daily snapshot, mark handled, reopen, counters) | `FirestoreStore` (production and the emulator), `MemoryStore` (unit tests) |
| Task queue | `TaskQueue` (`enqueue(client_id, delay)`) | `CloudTasksQueue`, `FakeQueue` |
| Slack | `Alerter` (`send(message)`) | `SlackWebhookAlerter`, `FakeAlerter`, `NullAlerter` (the hosted demo) |
| Clock | `Clock` (`today()`, `now()`) | system, fixed |

Boundaries that matter:

- **Rules end, the model begins.** A fault with one correct fix is a rule and never reaches the model as a question. The model receives the check results, the seeded data and the fix list, and ranks risk types from a closed list. See decision 0001.
- **Code owns identity and arithmetic.** The model returns a risk type and wording. The ID, the suppression, the cap and every number shown come from code.
- **The hosted worker never calls a paid model.** It is built with `RecordedRiskModel` only; the `openai` package is not in the production image.
- **The frontend never talks to Firestore or to Cloud Run from the browser.** The browser calls the frontend's own server routes; they add the proxy secret and the actor (sandbox session or admin).

## Data model

Firestore, Native mode.

| Path | Holds |
|---|---|
| `clients/{clientId}` | name, domain, `seeded: true`, `handled`: map of risk ID to `{handled_at, until}` (shared scope) |
| `clients/{clientId}/snapshots/{YYYY-MM-DD}` | checks, fixes, `ranked` (up to eight risks in model order), `visible` (the first five not suppressed), `suppressed`, prompt version, model name, `model_source: recorded`, input hash, run times |
| `sandboxes/{sessionId}/clients/{clientId}` | the visitor's own `handled` map and `visible` list for today, `expires_at` (TTL policy, one day) |
| `live_checks/{domain}` | the cached result of a typed-domain check, `expires_at` (TTL policy, ten minutes of use, deleted within a day) |
| `counters/live-{YYYY-MM-DD}` | the day's count of live checks; `counters/ip-{hash}-{window}` per address |

Two transactions, one function each, both parameterised by scope (shared or one sandbox):

- **Daily write.** Read the scope's handled map and today's snapshot; compute `visible` and `suppressed` from `ranked`; write the snapshot.
- **Handled / reopen.** Read the handled map and today's snapshot; change the map; recompute `visible`; write both.

Both read what they overwrite, so Firestore retries whichever commits second. `visible_risks(ranked, handled, today)` is one pure function used by both.

A risk: `{id: "<type>:<domain>", type, title, why, evidence: [input field names]}`. A fix: `{type, source: "dns" | "seeded", instruction}`.

An eval case (`evals/cases/NN-name.json`): `{set: "table" | "open", input: <exactly what the model receives>, label: {expected: [...], acceptable: [...], wrong: [...]}, note}`. The input is `SnapshotInput` in `backend/src/domain_health/models.py`, whose validators refuse a combination that cannot happen. `backend/src/domain_health/evals/table.py` is the rubric read as a table: it checks the cases and is the rules-only baseline. It is never an input to the model, a prompt or the pipeline (decision 0010). `backend/src/domain_health/evals/comparison.py` holds the rule for "the model does better than the baseline on the open cases".

## Stack and why

| Choice | Record |
|---|---|
| Rules for fixes, a model for ranked risks from a closed list, IDs in code | [0001](decisions/0001-rules-and-model.md) |
| OpenAI structured outputs, `gpt-6-luna`, reasoning off, temperature to be verified | [0002](decisions/0002-model.md) |
| One model interface; recorded output on the hosted demo; typed domains get no model call | [0003](decisions/0003-model-seam-and-recordings.md) |
| Firestore: a snapshot per client per day, transactions, two scopes | [0004](decisions/0004-firestore-and-the-handled-loop.md) |
| Cloud Run, Cloud Scheduler, Cloud Tasks, with guards; Vercel for the frontend, with a bundled fallback | [0005](decisions/0005-hosting.md) |
| Backend: Python 3.14, FastAPI, uv, dnspython | [0006](decisions/0006-backend-stack.md) |
| Frontend: Next.js 16, TypeScript strict, Tailwind 4, pnpm | [0007](decisions/0007-frontend-stack.md) |
| Evals scored in code against four bars, labels signed off in Phase 0 | [0008](decisions/0008-evals.md) |
| Two sets of cases, a rules-only baseline, tighter definitions | [0010](decisions/0010-measure-after-the-challenge.md) |
| Rubric objections not taken | [0011](decisions/0011-rubric-objections-not-taken.md) |
| Auth: OIDC for machines, a proxy secret, an admin session, a visitor sandbox | [0009](decisions/0009-auth.md) |
| Each runtime dependency | [dependencies](decisions/dependencies.md) |

## Security

The reviewer's checklist in security mode.

- **Machine auth.** `/internal/*` verifies a Google-signed OIDC token: signature against Google's keys, issuer, audience equal to the service URL, email equal to the invoker service account. Tested in CI with locally signed tokens and a fake key set. The Cloud Run service allows unauthenticated invocations at the platform level because the frontend cannot mint Google tokens; the app refuses everything it should.
- **Public API.** `/api/*` requires the proxy secret header, compared in constant time. Shared-state writes also require the admin actor, which only the frontend's server routes can assert after checking the admin session cookie.
- **Sessions.** Cookies are signed, `HttpOnly`, `Secure`, `SameSite=Lax`. Write routes check the `Origin` header. The admin passphrase is compared in constant time and sign-in attempts are rate limited.
- **Untrusted input.** The typed domain is validated as a public host name before any lookup and is only ever used as a DNS query name; the backend makes no HTTP request to it. DNS answers are untrusted text: length-capped, parsed, never rendered as HTML. Model output is untrusted: validated against the schema and the rules in the spec, rendered as text.
- **Spend and abuse.** Per-address limit, daily cap and query cap on the live check; counters in Firestore so they hold across instances and restarts; one instance at most; a budget alert. A GET never does metered work beyond a cached read. Limits are tested by firing requests at once, not one at a time.
- **Secrets.** None in the repository, the image or the client bundle. `NEXT_PUBLIC_` variables hold nothing secret.
- **Exposure.** No real company, person, client name or platform name in the tree or the history. Seeded domains are on reserved names.
- **Least privilege.** One service account runs the service (Firestore user, Tasks enqueuer); one invokes it (used by Scheduler and Tasks). Neither is an owner or editor.

## Testing

- Unit tests with the fixture resolver, the fixture model, the memory store and a fixed clock. Tests first for checks, rules, validation, suppression and scoring.
- Firestore emulator tests for the two transactions, the race, idempotency and the counters. The emulator needs a JDK of 21 or later; `make` points it at one.
- API tests through FastAPI's test client, including every refusal in the spec.
- Frontend: type check, lint, component tests for the pure view logic, a build.
- Screens: screenshots of every state in both themes at 1440 and 390 pixels wide, taken by a script and looked at by the verifier.
- Hosted: a real browser against the deployed site from the first deploy.
- Nothing in `make check` or CI touches real DNS, OpenAI, Google Cloud or Slack.

## Deployment

- **Backend.** `make deploy-backend` builds the image with Cloud Build and deploys to Cloud Run in `us-central1`: at most one instance, none when idle, request-based billing. `make infra` creates, and is safe to rerun: Firestore (Native, `us-central1`) with its TTL policies, the Cloud Tasks queue, the Cloud Scheduler job, the two service accounts, the secrets and the budget alert. The run executes both from the owner's machine with the `domain-health` gcloud configuration. A merge to `main` does not deploy the backend by itself; the phase that changes it deploys it and checks it.
- **Frontend.** Vercel, connected to the repository: a merge to `main` deploys production. Root directory `frontend/`.
- **Seeding.** `make seed` writes the twelve clients. The daily job does the rest.
- **Fallback data.** `make fallback` regenerates `frontend/src/data/fallback.json` from the same fixtures and recordings the worker uses; a test fails if it is out of date.
