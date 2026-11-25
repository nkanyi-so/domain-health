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
| DNS | `Resolver` (`txt(name)` returns records, no-such-name, timeout or too-large: an answer of more than 100 records or with a record over 4,096 characters is never cut and read in part) | `LiveResolver` (real DNS, TXT only; a server failure reads as a timeout), `FixtureResolver` (zone data in `backend/fixtures/zones/`). `CountingResolver` wraps either and refuses the forty-first lookup for one domain |
| Language model | `RiskModel` (`rank(snapshot_input)` returns a validated ranked list) | `OpenAIRiskModel` (live; only `make eval-live` and `make record` build it), `RecordedRiskModel` (replays committed recordings by input hash; the deployed worker and `make eval` use it), `FixtureRiskModel` (scripted; tests) |
| Database | `SnapshotStore` (read snapshot, write daily snapshot, mark handled, reopen, counters) | `FirestoreStore` (production and the emulator), `MemoryStore` (unit tests) |
| Task queue | `TaskQueue` (`enqueue(client_id, delay)`) | `CloudTasksQueue`, `FakeQueue` |
| Slack | `Alerter` (`send(message)`) | `SlackWebhookAlerter`, `FakeAlerter`, `NullAlerter` (the hosted demo) |
| Clock | `Clock` (`today()`, `now()`) | system, fixed |

Where Phase 1 put things (`backend/src/domain_health/`): `resolver/` (the interface and its two implementations), `checks/` (`spf.py`, `dkim.py`, `dmarc.py`, and `run.py`, which gives each check eight seconds), `rules.py` (the fix list), `domain_name.py` (is the typed text a public domain name), `seeded/` (the twelve clients; their days are in `backend/fixtures/clients/`, their DNS in `backend/fixtures/zones/`), `check_domain.py` (`make check-domain`).

Where Phase 3 put things: `store/__init__.py` (the documents' shapes, the `SnapshotStore` interface, `visible_risks` and every rule about what a write holds, as pure functions), `store/memory.py` and `store/firestore.py` (the two stores: each reads, calls those functions and writes, so they cannot differ in what they decide), `clock.py`, `worker.py` (`run_client`: one seeded client, one day; `python -m domain_health.worker <client-id> --prompt <file> --model <name>` is a dry run that prints the document and touches no database).

Where Phase 4 put things: `app.py` (every route, built from a `Deps` of interfaces), `serve.py` (the deployed service: `Deps` from the real parts; `DOMAIN_HEALTH_DEV=1` builds a local one on the emulator), `settings.py`, `machine_auth.py` (the OIDC check and Google's key set), `tasks.py` and `cloud_tasks.py`, `alerts.py` and `slack.py`, `seeded/recordings.py` (which recorded answers are kept; the service loads this), `seeded/recording_report.py` (the recordings read against the rubric's table; the service never loads it), `seeded/record.py` (`make record`, paid), `seeded/seed.py` (`make seed`). The cloud scripts are `scripts/infra.sh`, `scripts/deploy-backend.sh` and `scripts/seed.sh`, over `scripts/cloud-common.sh`, which pins every gcloud call to the `domain-health` configuration; the image is `backend/Dockerfile`, built by `backend/cloudbuild.yaml`.

Where Phase 5 put things, so far. `seeded/fallback.py` is `make fallback`: it builds the app over a store in memory with a fixed clock and the kept recordings, runs the worker's `run_client` for the twelve clients, calls `GET /api/clients` and each `GET /api/clients/{id}/snapshot` as the shared actor with nothing handled, and writes `frontend/src/data/fallback.json` as `{generated_for_day, clients, snapshots: {<client id>: page}}`. The day is fixed at 2026-01-04, run at 06:00 UTC: its ordinal divides by six, so every client, on a cycle of two or three days, is on the first day of its story, and the command writes the same bytes on any date. `api_types.py` is `make api-types`: it writes `frontend/src/lib/api-types.ts` from the app's OpenAPI schema (the request body and 200 response of every `/api/*` route and the types they reach, plus an `ApiRoutes` table of which route takes and gives what), and stops on a schema construct it does not know. Both files are written already in the frontend formatter's style, so each is compared byte for byte by a backend test (`tests/test_fallback.py`, `tests/test_api_types.py`), and the deployed service loads neither module (`tests/test_imports.py`).

Where Phase 5 put the rest. Two more backend commands, neither loaded by the deployed service: `eval_summary.py` is `make eval-summary`, which copies the totals the eval page shows (measures and bars, each set beside the rules-only baseline, counts, prompt version, model; every key named, so no row for a single case) out of `evals/results.json` into `frontend/src/data/eval-summary.json`, compared byte for byte by `tests/test_eval_summary.py`; `seeded/dev_snapshots.py` writes today's snapshots for the twelve clients into the local emulator with the worker's own `run_client`, refuses any address that is not the local emulator, and is run by `scripts/dev.sh` before the two servers start, because the emulator starts empty and nothing runs the daily job locally.

Where Phase 6 put things.

- The report. `frontend/src/lib/view/report.ts` is pure: `buildReport` takes the same snapshot view the client page draws (`clientPageView` over `loadClientPage`, so the visitor's own handled list, or the bundled snapshot when the backend is away) and gives one model with four sections in a fixed order: authentication, reputation, sending, actions, the fixes numbered first and the advisory risks after them under the page's marking. Two renderers read that one model: `reportMarkdown` in the same file (text from the snapshot is escaped, records go in code spans, no HTML is written) and `frontend/src/components/report.tsx` (React, so every string is rendered as text). `/clients/[id]/report` is the page; `/clients/[id]/report.md` is a route handler that returns the Markdown as `text/markdown` with a file name of the client and the day, and 404 for an unknown client or no snapshot. Both only read. The marking's words live once, in `frontend/src/lib/view/advisory.ts`, for the page and the report. The print rules are at the end of `frontend/src/app/globals.css`.
- The read cache. `read_cache.py` is a small cache with a time to live of 30 seconds and a bound of 256 entries, oldest dropped first; it takes the time from its caller and imports nothing. `create_app` in `app.py` makes one for each app and keeps in it the answers of `GET /api/clients` and `GET /api/clients/{id}/snapshot`, the 404 "no snapshot for that day" included, keyed by route, client, day and the caller's scope (shared, or one sandbox session). A handled or reopen click drops that caller's entries before it answers; a worker run that writes clears the cache; a read that either of those overtook is not kept; an error is never kept. It is coherent because the service is one instance at most: with more, another instance's click or worker run would show up to 30 seconds late. The live check and the machine routes do not use it. `tests/test_read_cache.py` holds it.

Where Phase 6 put the README's numbers. `readme_tables.py` is `make readme`: it rewrites the parts of `README.md` that sit between pairs of HTML comments (`<!-- name:start -->`, `<!-- name:end -->`) and nothing else. The eval table, each set's numbers and the prompt wording come from `evals/results.json`, with the rules-only baseline's totals and the open set's counts for each run scored by `eval_summary.py`'s own code; the table of attempts is every prompt version and model with committed recordings, scored again by the harness, with costs from `evals/ledger.jsonl`; the build's numbers are counted from `docs/RUN_LOG.md` for Phases 0 to 6. `tests/test_readme.py` holds the README to it: the generated parts are current, every "N in 144" is the results file's count for whoever the line names, the claim and its limit stand word for word, and the spend is the plan's. The deployed service does not load the module (`tests/test_imports.py`).

The frontend (`frontend/src/`):

- `lib/server/` runs on the server only. `env.ts` reads `BACKEND_URL`, `PROXY_SECRET`, `SESSION_SECRET` and `ADMIN_PASSPHRASE` when a request needs them: outside production a missing one falls back to the local backend and a dev-only value; in production a missing one, or a dev-only secret, is an error, and `REPO_URL` (optional, not secret) is the address behind the "Source" links. `session.ts` signs and checks the two cookies (`dh_session`, a visitor's sandbox, seven days; `dh_admin`, twelve hours), each `<kind>.<id>.<expiry>.<HMAC-SHA256>`, `HttpOnly`, `SameSite=Lax`, `Secure` except on a local address over http. `actor.ts` picks the `X-Actor`: `admin` on a valid admin cookie, else the visitor's sandbox, else one fixed empty sandbox that is only ever read, so looking at a page sets no cookie; a visitor's session is made by their first write. `request.ts` holds the `Origin` check and the one client address (first entry of `x-forwarded-for`, then `x-real-ip`, then `127.0.0.1`). `backend.ts` is the one call to the backend, with a timeout (12 s for a read, 15 s for a click, 30 s for a live check): a network error, a timeout or a 5xx is "unreachable", a 4xx is "refused" and never falls back. `rate-limit.ts` counts wrong sign-in tries in memory, per server instance: five from one address and thirty overall in ten minutes. `data.ts` holds the loaders the pages call directly; `routes.ts` and `click.ts` what the route handlers share.
- `app/api/`: `GET clients`, `GET clients/[id]/snapshot`, `POST clients/[id]/handled`, `POST clients/[id]/reopen`, `POST live-check`, `POST admin/sign-in`, `POST admin/sign-out`. Every POST refuses a request whose `Origin` is not its own host. The live check is a POST the page makes only when the visitor presses "Check domain"; an address `/check?domain=` fills the field and nothing more, so a shared link, a prefetch or a crawler spends nothing. A press of "Check domain" on the first screen leaves a one-shot marker in that tab's session storage and opens the address; the check page starts the check only when it finds the marker for that domain, left in the last thirty seconds, and removes it. The placeholder the check page draws while it loads has no domain and does not touch the marker. A sign-in attempt asks the limit, compares the passphrase and counts a wrong one in one step with nothing awaited in between, so tries made at once cannot get past the limit.
- `lib/view/` is the pure logic the tests cover: from what the backend answered to the view a screen draws (`screens.ts`), the states of a client's page and what a click does before the server answers (`client-page.ts`), the list's order (`clients.ts`), the live check's outcomes and refusal words (`live-check.ts`), the eval page's words (`evals.ts`), and dates, evidence words, check rows and figures.
- `data/demo-states.ts` holds the fixed views behind `?demo=<name>`, built from the bundled snapshots. `components/` holds the screens; only the advisory panel, the live check, the sign-in form, the sign-out button, the theme switch, the current-link marker and the live region run in the browser. Pages render on the server inside one `Suspense` each, whose fallback is the same screen in its loading state.
- When today has no snapshot, the page asks the backend for the day before (`?day=`) once and, if it is there, shows it with "Mark handled" switched off.
- `make screens` is `scripts/screens.sh` and `frontend/scripts/screens.mjs`. The shell script starts the Firestore emulator, writes today's snapshots into it as `make dev` does, starts the backend with `DOMAIN_HEALTH_DEV=1` on port 8000 and the frontend's development server on port 3000 (a production build refuses the development secrets, by design), waits for both and stops all of it when the run ends, however it ends. The Node script drives the Chromium build already in Playwright's cache through `playwright-core` (a development dependency pinned to the version that expects that build; nothing is downloaded and `make check` and CI do not use it). Sixteen states are opened at their `?demo=` address; state 16 is a real sign-in with the development passphrase and one real handled click on the emulator. The theme is set as the page itself decides it with nothing saved: by the system's preference. On every page it computes text contrast against the ground behind each piece of text, sideways overflow, and the outline of every control reached with the Tab key against the same control at rest, checks the state's wording and tab title, and exits non-zero on any failure; `/evals` and `/about` get the same checks without a screenshot. `docs/screens/README.md` is written by the run.

The API, as Phase 4 built it. Every `/api/*` call carries `X-Proxy-Secret` and `X-Actor` (`admin`, or `sandbox:<session>`); the live check also carries `X-Client-Address`, the visitor's address as the frontend's server saw it (one IP address and nothing else: a list, a port, a zone suffix or any other text is refused with 400; an IPv6 address is counted as its /64, and an IPv4 address written inside an IPv6 one as the IPv4 address), which is hashed before it names a counter.

| Route | Gives |
|---|---|
| `GET /health` | `{status: ok}`. Not `/healthz`: Cloud Run keeps that path. |
| `GET /api/clients` | the twelve clients, each with today's summary or `today: null` when today has no snapshot |
| `GET /api/clients/{id}/snapshot?day=` | the day as the actor sees it (today by default); 404 when that day has no snapshot. No earlier day is served in its place |
| `POST /api/clients/{id}/handled`, `/reopen` | body `{day, risk_id}`; the day after the click. 404 no snapshot, 422 no such risk, 503 busy |
| `POST /api/live-check` | body `{domain}`; checks and fixes, `cached` true when it is the answer kept from the last ten minutes. 422 with the refusal's name; 429 with `rate_limited` or `daily_cap` (no time is given for when the limit lifts) |
| `POST /internal/dispatch` | one task per client, two seconds apart; 502 if any could not be enqueued, after trying all |
| `POST /internal/worker/{id}?day=&dry_run=` | runs the client's day; a dry run returns the document and writes nothing |

The live check's order is fixed: the name is validated, then the cache is read, then one slot is taken from the two counters in one transaction (`counters/ip-{hash}-{window}`, five per ten-minute window, and `counters/live-{day}`, 200), and only then is DNS reached, over TCP. A cached answer takes no slot.

Seeded recordings: `backend/fixtures/recordings/<prompt version>/<model>/run-1..3/`. A state's answer is replayed only when its three recorded answers are valid and agree on their first five types; otherwise the snapshot says "risks unavailable".

A check either gives the fields the risk model receives (`Checks` in `models.py`) or is **unavailable**: a lookup it needed did not answer or answered with more text than a check reads, it ran out of time, or the domain's forty lookups were spent. Unavailable is never read as "no record", so it gives no fix. The model's input cannot hold an unavailable check; fixture zones always answer, so a seeded client's input is always whole, and the typed-domain path, which has no model call, shows the check as not made. Beside those fields a check keeps what they cannot say: the records as read, the problems in plain words, and DKIM keys that are not RSA (found, never called weak, not in `keys`, whose `key_bits` is an RSA length).

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
| `sandboxes/{sessionId}/clients/{clientId}` | the visitor's own `handled` map, `expires_at` (TTL policy, one day). The visitor's visible list is computed at each read and not stored (Phase 3) |
| `live_checks/{domain}` | the cached result of a typed-domain check, `expires_at` (TTL policy, ten minutes of use, deleted within a day) |
| `counters/live-{YYYY-MM-DD}` | the day's count of live checks; `counters/ip-{hash}-{window}` per address |

Two transactions, one function each, both parameterised by scope (shared or one sandbox):

- **Daily write.** Read the scope's handled map and today's snapshot; compute `visible` and `suppressed` from `ranked`; write the snapshot.
- **Handled / reopen.** Read the handled map and today's snapshot; change the map; recompute `visible`; write both.

Both read what they overwrite, so Firestore retries whichever commits second. `visible_risks(ranked, handled, today)` is one pure function used by both.

How the two scopes differ in what is written (Phase 3):

- **Shared.** The daily write saves the day's snapshot with the view the client's handled map gives it. A click writes the client's `handled` field (no other field of that document) and the `visible` and `suppressed` of the snapshot it was made on.
- **A sandbox.** Nothing shared is ever written from it. A click writes the visitor's own document, which holds only the marks. A visitor who has marked nothing has no document, and a reopen by such a visitor makes none.
- **A read writes nothing, and computes the view.** In either scope a read takes the day's `ranked` and the scope's marks and calls `visible_risks`. It does not trust the list stored in the snapshot: a click made on yesterday's page after today's snapshot exists changes the marks and yesterday's stored list, not today's, and the risk must still be hidden today. The stored list is what the daily write and the last click on that day left; the API serves the computed one.
- **A sandbox lives one day from its first click.** `expires_at` is a real timestamp, for the TTL policy; a later click does not move it. Firestore deletes some time after it, so every read treats a document past `expires_at` as absent. A session ID, a client ID and a typed domain are each checked before they are used as a document's name, in the store itself.
- **A click** names the snapshot's day and a risk ID. An ID that is not among that day's `ranked` is refused and never stored, and so is a click on a day with no snapshot. A mark holds `handled_at` and `until`, the first UTC day the risk may show again: the day of the click plus thirty.
- **The snapshot** also holds the seeded sources, what each check found beyond the model's fields (records, problems), `risks_status` (`ranked` or `unavailable`, with the reason) and the run's `started_at` and `finished_at`. Days are UTC days.
- **A change the database aborts is run again.** The Firestore library retries a transaction aborted at its commit and raises one aborted while reading. The store runs an aborted change again from the start, up to eight times with a short random wait, then raises `StoreBusyError` with nothing changed.
- **`live_checks/{domain}`** holds the checks and fixes of a typed domain, `checked_at` and `expires_at` (ten minutes on); a read after that gives nothing. The counters come in Phase 4.

A risk: `{id: "<type>:<domain>", type, title, why, evidence: [input field names]}`. A fix: `{type, source: "dns" | "seeded", instruction}`.

An eval case (`evals/cases/NN-name.json`): `{set: "table" | "open", input: <exactly what the model receives>, label: {expected: [...], acceptable: [...], wrong: [...]}, note}`. The input is `SnapshotInput` in `backend/src/domain_health/models.py`, whose validators refuse a combination that cannot happen. `backend/src/domain_health/evals/table.py` is the rubric read as a table: it checks the cases and is the rules-only baseline. It is never an input to the model, a prompt or the pipeline (decision 0010). `backend/src/domain_health/evals/comparison.py` holds the rule for "the model does better than the baseline on the open cases", which is reported and is not a bar (decision 0012).

## Stack and why

| Choice | Record |
|---|---|
| Rules for fixes, a model for ranked risks from a closed list, IDs in code | [0001](decisions/0001-rules-and-model.md) |
| OpenAI structured outputs, `gpt-6.1-terra` (it was `gpt-6-luna` until Phase 2 measured it), reasoning off, temperature 0 | [0002](decisions/0002-model.md) |
| One model interface; recorded output on the hosted demo; typed domains get no model call | [0003](decisions/0003-model-seam-and-recordings.md) |
| Firestore: a snapshot per client per day, transactions, two scopes | [0004](decisions/0004-firestore-and-the-handled-loop.md) |
| Cloud Run, Cloud Scheduler, Cloud Tasks, with guards; Vercel for the frontend, with a bundled fallback | [0005](decisions/0005-hosting.md) |
| Backend: Python 3.14, FastAPI, uv, dnspython | [0006](decisions/0006-backend-stack.md) |
| Frontend: Next.js 16, TypeScript strict, Tailwind 4, pnpm | [0007](decisions/0007-frontend-stack.md) |
| Evals scored in code against four bars, labels signed off in Phase 0 | [0008](decisions/0008-evals.md) |
| Two sets of cases, a rules-only baseline, tighter definitions | [0010](decisions/0010-measure-after-the-challenge.md) |
| Rubric objections not taken | [0011](decisions/0011-rubric-objections-not-taken.md) |
| The claim says what is measured; the baseline comparison is evidence | [0012](decisions/0012-the-claim-says-what-is-measured.md) |
| Auth: OIDC for machines, a proxy secret, an admin session, a visitor sandbox | [0009](decisions/0009-auth.md) |
| The service is opened by turning off Cloud Run's invoker check | [0014](decisions/0014-the-service-is-opened-by-turning-off-the-invoker-check.md) |
| Each runtime dependency | [dependencies](decisions/dependencies.md) |

## Security

The reviewer's checklist in security mode.

- **Machine auth.** `/internal/*` verifies a Google-signed OIDC token: signature against Google's keys, issuer, audience equal to the service URL, email equal to the invoker service account. Tested in CI with locally signed tokens and a fake key set. The Cloud Run service is open at the platform level because the frontend cannot mint Google tokens; the app refuses everything it should. It is opened by turning off Cloud Run's invoker check (`--no-invoker-iam-check`), not by granting `allUsers`, which the project's organisation policy refuses (decision 0014): the app-level checks are the only gate.
- **Public API.** `/api/*` requires the proxy secret header, compared in constant time. Shared-state writes also require the admin actor, which only the frontend's server routes can assert after checking the admin session cookie.
- **Sessions.** Cookies are signed, `HttpOnly`, `Secure`, `SameSite=Lax`. Write routes check the `Origin` header. The admin passphrase is compared in constant time and sign-in attempts are rate limited.
- **Untrusted input.** The typed domain is validated as a public host name before any lookup and is only ever used as a DNS query name; the backend makes no HTTP request to it. DNS answers are untrusted text: length-capped, parsed, never rendered as HTML. Model output is untrusted: validated against the schema and the rules in the spec, rendered as text.
- **Spend and abuse.** Per-address limit, daily cap and query cap on the live check; counters in Firestore so they hold across instances and restarts; one instance at most; a budget alert. A GET never makes a DNS lookup or a model call. It does read Firestore, about two documents a client for the list and two to four for a client page or its report, but only on the first load: the service keeps each answer for 30 seconds (`read_cache.py`), so repeated loads of the same page cost no reads. What is still not capped is distinct pages over time, handled and reopen clicks (each a Firestore read and write), the live check's cache read and counter transaction on every request, and Cloud Run time, all bounded in rate by the one instance (in `docs/DECISIONS_TO_REVIEW.md`). Limits are tested by firing requests at once, not one at a time.
- **Secrets.** None in the repository, the image or the client bundle. `NEXT_PUBLIC_` variables hold nothing secret.
- **Exposure.** No real company, person, client name or platform name in the tree or the history. Seeded domains are on reserved names.
- **Least privilege.** One service account runs the service (Firestore user, Tasks enqueuer); one invokes it (used by Scheduler and Tasks). Neither is an owner or editor. A third builds the image (reads the uploaded source, writes the image and its log): a new project's default build account has no access to the source, and using it would have meant widening it.

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
