# Plan: domain-health

This file is the single record of progress; `docs/RUN_LOG.md` beside it is the run's event log, written by scripts and committed with this file. Each phase lands as its own branch (`phase-<number>-<words>`) and pull request; the description links to the phase log here. A gate is ticked only when its evidence (the commands run and their real output) is written in the phase log. Never start a phase before the previous gate is ticked. Gates, checklist items and phase headings are changed only by the owner: a run may tick boxes and add lines, and the merge gate refuses anything else.

## Status

Kept current by the build at every change of state, so progress can be read here without any log.

| Phase | State | Pull request |
|---|---|---|
| 0: scaffold, process layer and the measure | building | [#1](https://github.com/nkanyi-so/domain-health/pull/1) |
| 1: checks and rules | not started | |
| 2: the model and the evals | not started | |
| 3: snapshots and the handled loop | not started | |
| 4: schedule, worker, API, first backend deploy | not started | |
| 5: the screens | not started | |
| 6: report, README, release checks | not started | |

States: `not started`, `building`, `in review`, `waiting on you`, `merged`, `merged, checked live`. Mark a checkpoint phase with "(checkpoint)" after its name. On the default branch the newest merged phase still reads `in review`, because its row was written before the merge; the next phase's first commit corrects it, and after the last phase a row left at `in review` means merged.

No phase is a checkpoint. Phase 0 is merged by the owner. Phases 1 to 6 are merged by the run through the merge gate, unless the gate leaves one for the owner.

Spend: $0.00 of $10 cap
Decisions to review: 6 (`docs/DECISIONS_TO_REVIEW.md`)

Paid steps this plan lists (they run without asking while the worst case stays under the cap):

| Phase | Step | Worst case |
|---|---|---|
| 2 | one call to test whether `temperature` is accepted | $0.01 |
| 2 | `make eval-live`, up to six times on `gpt-6-luna` (60 calls each) | $0.30 |
| 2 | `make eval-live`, up to four times on `gpt-6.1-terra`, only if Luna misses a bar | $2.00 |
| 4 | `make record` for every seeded client state, up to three times | $0.20 |
| 4 to 6 | Google Cloud outside the free tier (image storage, builds) | $1.00 |

Estimated total: under $3.50. Everything else is free.

## Waiting on you

Nothing.

<!-- When the build stops, "Nothing." is replaced by one block, everything it needs at once:
what stopped and why, in plain words; each question numbered, with the options, what each costs,
and the recommended answer; what the build will do once it has the answers. The same text goes
into a GitHub issue assigned to the owner (`.claude/hooks/stop.sh open`). When answered, the
block goes into the phase log with the answers, and this section says "Nothing." again. -->
<!-- end: waiting on you -->

---

## Phase 0: scaffold, process layer and the measure

The owner merges this phase, so it carries everything the owner must sign off once: the guards, the commands, the measure.

- [ ] Project scaffold: `backend/` (Python 3.14, uv, ruff, mypy strict, pytest) and `frontend/` (Next.js 16, TypeScript strict, ESLint, Tailwind 4, pnpm), each with one real passing test.
- [ ] `Makefile` with `setup` (installs both toolchains, runs `git config core.hooksPath .githooks`, warns if gitleaks is missing or no JDK of 21 or later is found), `dev`, `check` (both toolchains, emulator tests included), `format` (formats the one file passed as `FILE=`), `eval` (prints "no prompt yet: nothing to measure" until Phase 2), and stubs that fail with "not built yet" for `eval-live`, `record`, `seed`, `infra`, `deploy-backend`, `fallback`, `screens`.
- [ ] Harness layer adapted to this stack: allow list in `.claude/settings.json` (never `eval-live`, `record`, `infra`, `deploy-backend`, `seed`), `protected-paths.txt`, `measure-paths.txt` corrected to the files that now exist, CI setup steps for both toolchains and the emulator, actions pinned by commit. List every change in the log.
- [ ] CI has three jobs: `check`, `secrets`, and `eval` (runs `make eval STRICT=1`).
- [ ] `.gitignore` (with `.env`), `.env.example` naming every variable from `docs/STANDING.md` and the deploy.
- [ ] No `*.harness-new` file left: each one merged by hand and deleted.
- [ ] `evals/RUBRIC.md`: the closed list of risk types (about twelve), each with when a specialist flags it, when it is acceptable and when it is wrong; the same for the line between a fix and a risk. A test asserts the code's list of types equals the rubric's.
- [ ] `evals/cases/`: twenty labelled snapshots in the shape in `docs/ARCHITECTURE.md`, at least six hard, at least four healthy; every risk type expected in at least one case and wrong in at least one. A schema test loads all twenty. Labels second-read by a separate agent against the rubric; what it changed is in the log.
- [ ] `evals/bars.toml` with the four bars from `docs/SPEC.md`.
- [ ] `docs/CLAIM.md` and `backend/tests/test_claim_wording.py`, which checks the sentence in `README.md`, `frontend/src/content/claim.ts` and `backend/src/domain_health/report/templates/` wherever those exist.
- [ ] `scripts/preflight-project.sh`, called by `.claude/hooks/preflight.sh`: confirms every owner action in `docs/STANDING.md` that a script can confirm (the OpenAI key answers for `gpt-6-luna`; the `domain-health` gcloud configuration exists, is signed in with a user account and points at `GCP_PROJECT_ID`; billing is enabled on that project; the login may create budgets; `vercel whoami` answers; Node 24 and a JDK of 21 or later are present). It reads names, never prints values.
- [ ] Branch protection on `main`: no force-push, status checks required with this project's CI jobs picked as the required checks (`check`, `secrets`; not `eval`), and it applies to administrators too (a classic rule with "Do not allow bypassing", or a ruleset with an empty bypass list). The deny rules in settings are a courtesy; this is the guard. In run-through mode the merge gate checks it and merges nothing without it, so if it cannot be turned on, say so under "Waiting on you".
- [ ] `docs/STANDING.md` is filled in and lands on `main` with this phase. Every owner action in it is ticked or listed under "Waiting on you". `bash .claude/hooks/preflight.sh` output is in the log.

**Gate:** `make check` exits 0 with at least one passing test in each toolchain and the twenty cases loading. The pre-commit hook refuses a commit when a test is made to fail (show it, then undo). CI runs green on the first push, all three jobs. Branch protection is shown to be on. `bash .claude/hooks/preflight.sh` ends with `preflight: ready`. The owner merges this phase in both modes: it changes the guards and sets the measure.

**Log:**

### 2026-11-19: step list and risks (written before the work)

Where things stood: branch `phase-0-scaffold` holds the blueprint commit only; no pull request, no stop, nothing to undo. `bash .claude/hooks/preflight.sh` reported two things missing, `OPENAI_API_KEY` and `GCP_PROJECT_ID`. Both are owner actions already listed in `docs/STANDING.md`; nothing in this phase's build needs either, so the phase is built first and they are asked for once, with the merge, under "Waiting on you".

Steps:

1. Backend scaffold in `backend/`: `uv`, Python 3.14, FastAPI app with a health route, ruff, mypy strict, pytest, one real test. The closed lists (risk types, fix types) and the pydantic models for the model's input and an eval case go in now, because the measure is written against them.
2. Frontend scaffold in `frontend/`: Next.js 16 App Router, TypeScript strict, ESLint, Prettier, Tailwind 4, pnpm, one real test and a build.
3. Firestore emulator wiring (pinned `firebase-tools` in `emulator/`), with one smoke test that it answers, so `make check` and CI already run emulator tests and Phase 3 does not have to touch CI.
4. `Makefile`: `setup`, `dev`, `check`, `format`, `eval`, and the "not built yet" stubs.
5. The measure: `evals/RUBRIC.md`, twenty cases in `evals/cases/`, `evals/bars.toml`, `docs/CLAIM.md`, `backend/tests/test_claim_wording.py`, and tests that the code's types equal the rubric's, that all twenty cases load, and that the set has the mix the plan asks for. Then a second read of every label by a separate agent.
6. Harness layer: allow list, `protected-paths.txt`, `measure-paths.txt`, CI (`check` with both toolchains and the emulator, `secrets`, `eval`), actions pinned by commit, `scripts/preflight-project.sh` called from the preflight hook. `.gitignore`, `.env.example`.
7. `make check` green, the pre-commit refusal shown, push, CI green, branch protection shown.
8. Reviewer, verifier, challenger; evidence; stop for the owner's merge.

Verifier: needed. There is something to run: `make setup`, `make check`, `make dev`, `make eval`, the stubs, the pre-commit hook.

Challenger: needed. This phase writes the claim pin and the whole measure (rubric, cases, labels, bars). There are no eval results yet, so it reads the measure, not scores.

Risks seen:

- The rubric has to be exact enough for a second reader to check a label, and the more exact it is, the more a table of thresholds could produce the same labels without a model. The rubric keeps the judgment in the context clauses (the same value is expected, acceptable or wrong depending on other fields). The challenger's third question is aimed at exactly this, and its answer goes to the owner unedited.
- The model's input shape is fixed here, before the checks exist. Phase 1 has to produce this shape; if a check needs a field the cases lack, that touches the cases and is the owner's to merge.
- This machine's default Node is 20 and default JDK is 17. Node 24 (nvm) and JDK 23 are installed; the Makefile has to find them without changing the machine.
- Every guard file is touched in this phase by design. The owner merges it.
- `preflight: ready` cannot be reached by the build: it needs the owner's key and project. That gate line stays unticked until the owner has done them.

### 2026-11-19: what was built

- `backend/`: uv project on Python 3.14; FastAPI app with `/healthz`; the two closed lists (`types.py`); the model's input (`models.py`); the eval case and its loader (`evals/cases.py`); `python -m domain_health.evals` behind `make eval`. Ruff, mypy strict (with the pydantic plugin), pytest. 40 tests, one of them marked `emulator`.
- `frontend/`: Next.js 16.4.6, React 19.3, TypeScript strict, ESLint (explicit types on exports are an error), Prettier, Tailwind 4.3, vitest. One page showing the claim; one test that the page's claim is the line in `docs/CLAIM.md`.
- `emulator/`: pinned `firebase-tools` 15.37.0 and `firebase.json`.
- `Makefile` and `scripts/` (`dev.sh`, `format-one.sh`, `toolchain-check.sh`, `preflight-project.sh`). `.gitignore`, `.env.example`.
- The measure: `evals/RUBRIC.md` (12 fix types, 13 risk types, the line between them), `evals/cases/` (20 cases: 9 hard, 7 healthy with nothing expected and no fix), `evals/bars.toml`, `docs/CLAIM.md`, `backend/tests/test_claim_wording.py`.

Changes to the harness layer, all of them (none removes or loosens a check):

- `.claude/settings.json`: five lines added to the allow list, each an exact command with no wildcard: `make eval`, `make eval STRICT=1`, `make dev`, `make screens`, `make fallback`. (Two more, `make format *` and `make check-domain *`, were in the first commit and were taken out after the review below.) Not added, so they always ask: `eval-live`, `record`, `infra`, `deploy-backend`, `seed`. Deny list and hooks unchanged.
- `.claude/hooks/protected-paths.txt`: four generated paths added (`evals/results.json`, `evals/recordings/*`, `frontend/src/data/fallback.json`, `docs/RUN_LOG.md`).
- `.claude/hooks/measure-paths.txt`: the five intake lines all name files that now exist; three added: `frontend/src/content/claim.test.ts`, and after the second review `backend/src/domain_health/types.py` and `backend/tests/test_rubric_types.py`.
- `.claude/hooks/preflight.sh`: calls `scripts/preflight-project.sh` and adds its MISSING count to its own; a missing project script is itself MISSING.
- `.github/workflows/ci.yml`: the `check` job's placeholder is replaced by setup for uv, pnpm, Node 24 and JDK 21 and the three installs; a third job, `eval`, runs `make eval STRICT=1`. `secrets` is unchanged. Actions pinned by commit: `astral-sh/setup-uv` v10.3.3, `pnpm/action-setup` v6.1.1, `actions/setup-node` v7.1.0, `actions/setup-java` v6.3.0, beside the existing `actions/checkout` pin.
- `.githooks/pre-commit`, the agents and the skill: unchanged.
- No `*.harness-new` file existed: `find . -name '*.harness-new' -not -path './.git/*'` prints nothing.

Libraries, checked against what was installed (principle 6):

- Starlette's test client deprecates `httpx` in favour of `httpx2`; the dev group uses `httpx2`. Phase 4's webhook client (`httpx` in `docs/decisions/dependencies.md`) should check this again.
- `create-next-app@16` now writes `cacheComponents: true` and `partialPrefetching: true` and loads Tailwind through `@tailwindcss/turbopack`, not PostCSS. Kept as generated. Phase 5 reads `frontend/node_modules/next/dist/docs/` before writing a route: with cache components on, anything that reads a cookie has to sit under a suspense boundary.
- `frontend/AGENTS.md` is written by Next and re-created by `next dev`; it is committed as generated.
- `pydantic-settings` is not installed yet (see the decisions file).

### 2026-11-19: second read of the labels

A separate agent, given only the rubric and the case files, labelled all twenty cases itself and compared.

Its result, in its words: "20 of 20 labels agree with the rubric. All 20 `input.fixes` lists match the fix table exactly, with the right `source`. No type appears in two lists, and no case expects more than five."

It also reported twelve places where the rubric was unclear, and ten objections "as a specialist". What was changed because of it, before the first commit:

- Rubric, made exact: `pct` is 100 when a valid record sets none; the windows of the rates; what `listings_90d` and `days_since_delisted` count; the `instruction` field; "a readable SPF record" (an over-limit record is readable); a previous week of 0; no previous open rate; the order the lines are read in (`wrong`, `expected`, `acceptable`) and that the gaps are deliberate; a sub-1,024 key is wrong for `dkim_key_1024` whatever the other keys are; the scope of the 2.0 ratio in `volume_spike`; consequence 2 applies to the record a type is about.
- Rubric, changed in substance: `spf_weak_all` (see the decisions file). This was its objections 1 and 2.
- Input model: `open_rate_prev_pct` may be null.
- Cases: 07 (ratio moved off the 1.2 boundary; no earlier open rate; now nothing expected), 12 (`p=none` added so `?all` is expected under the new line), 16 (no earlier open rate; grade medium), 19 (grade medium; the note no longer calls the open-rate fall unrelated), 20 (complaints 0.15 added so it still expects five), and the notes of 08, 11 and 15.
- After the changes the labels were re-derived from the changed rubric line by line. They have not had a second read since the change: the challenger and the owner read them next.

Its objections that were not taken, for the owner, who is the specialist:

1. Low volume is cut at 1,000 a week; at 1,000 to 3,000 one or two complaints still make 0.10%, so "expected" there rests on very few complaints.
2. Low volume is a seven-day figure but gates the thirty-day open rate (case 04): the reason given for complaints does not hold as well for opens.
3. Open rate is inflated by mail privacy proxying; a specialist would weight a fall below complaints and reputation. Case 19 expects it alone.
4. `p=quarantine; pct=0` is a known deliberate setup that is in effect `p=none`; the rubric calls it enforcing with partial enforcement expected. `pct` is also being retired from the protocol.
5. Case 16 expects both `volume_spike` and `new_domain_volume`: one fact counted twice.
6. A DKIM key found in DNS is not proof that it signs mail (it agreed with "acceptable" for the mix).

### 2026-11-19: `make eval`

```text
$ make eval
no prompt yet: nothing to measure
$ make eval STRICT=1
no prompt yet: nothing to measure
```

No results file is written before a prompt exists, so there is none to commit in this phase.

### 2026-11-19: review, first run, on 0a7b46b

Verdict as reported: "one blocking finding. The code, tests and measure are sound. One guard in `.claude/settings.json` does not do what the checklist says it does."

Findings as reported, then what was done:

1. Blocking. "The allow list lets a paid or cloud target run without asking." `Bash(make format *)` and `Bash(make check-domain *)`: "the `*` also matches extra make goals and flags", so `make format FILE=Makefile eval-live` runs `eval-live` too, and `-f` or `--eval` run any recipe. Harmless only while those targets are stubs.
   - Done: both lines removed. Every `make` line left in the allow list is an exact command. (`make format` is run by the edit hook, which needs no allow line; `make check-domain` will ask.) The reviewer also proposed deny rules for the paid targets; those were not added, because a deny rule would stop the run-through from running the paid steps the plan lists at all. Instead the Makefile now refuses any of `eval-live`, `record`, `seed`, `infra`, `deploy-backend` unless it is the only goal:

   ```text
   $ make -n format FILE=Makefile eval-live
   Makefile:78: *** eval-live is paid or writes to Google Cloud: run it alone, as the only goal.  Stop.
   $ make -n check-domain DOMAIN=example.com record
   Makefile:78: *** record is paid or writes to Google Cloud: run it alone, as the only goal.  Stop.
   $ make -n -k seed infra
   Makefile:78: *** seed infra is paid or writes to Google Cloud: run it alone, as the only goal.  Stop.
   $ make eval-live
   make eval-live: not built yet
   ```
2. Not blocking. "Preflight can skip the Node and JDK check without saying so": if `make` fails before the toolchain script prints a warning, nothing is counted missing.
   - Done: `scripts/preflight-project.sh` now counts that as MISSING ("the Node and JDK check did not run").
3. Not blocking. "`make eval STRICT=1` only sees prompts named `risks-v*.md`": a prompt under another name prints "nothing to measure" and CI's `eval` stays green.
   - Done: anything in `prompts/` that is not a version file is an error, with or without `STRICT`. One test added.
4. Not blocking. "The import test that `CLAUDE.md` rule 1 describes does not exist yet." Nothing imports `dns`, `openai` or `google.cloud` yet; `backend/tests/test_emulator_smoke.py` imports `urllib.request` and must be a named exception when the test is written.
   - Not done here: Phase 1 adds the first outside system (DNS) and writes the import test with it, with the smoke test as a named exception until Phase 3 replaces it.

It also confirmed: the harness-change list matches the diff of `.claude`, `.githooks` and `.github`; the counts in this log; that no gate, checklist item or heading in this file was edited; and that the verifier and challenger statements at the top of this log are true.

### 2026-11-19: review, second run, on 8f9390e

Verdict as reported: "one blocking finding. The preflight gate cannot pass on the owner's Mac. Everything else holds up: the code, the measure, the CI changes and the fixes from the first review."

1. Blocking. `scripts/preflight-project.sh` called `make --eval`, which "arrived in GNU Make 3.82. This Mac's only `make` is `/usr/bin/make`, GNU Make 3.81", so "the Node and JDK check never runs on this machine" and the first review's fix "now always prints `MISSING: the Node and JDK check did not run`".
   - Done: the Makefile has a real `toolchain` target and the script calls `make -s toolchain`. On this Mac the preflight now prints `ok:      Node 24` and `ok:      JDK 23` (full output under the gate evidence).
2. Not blocking. The log said 39 tests; the review-fix commit made it 40.
   - Done: corrected above.
3. Not blocking, for the owner. "The labels can be produced by a fixed threshold table": the reviewer wrote "a mechanical reading of `evals/RUBRIC.md`, about 100 lines of if/else" that "reproduces every label in all 20 cases exactly" and every fix list. "So a rules engine with no model would score full marks on coverage, precision and harmful. Passing the bars would then not show 'judgment-call risks from a model'." It set this against the sentence in the risks above, "The rubric keeps the judgment in the context clauses".
   - Not changed, by its own instruction and the working loop's: this is a question about the measure, so it is the owner's. It is true, and the build's own drafting confirms it: the labels were drafted by applying the rubric mechanically. The risk sentence above was written before the work and is left as written; the fact is that the context clauses are themselves fixed conditions on other fields. It is question 1 under "Waiting on you". The reviewer's run is also a second reading of the five cases changed after the label check: "They all agree with the rubric as written."
4. Not blocking. `measure-paths.txt` did not list `backend/src/domain_health/types.py` or `backend/tests/test_rubric_types.py`, so a later phase could change the closed lists and the test that pins them together and be merged by the gate.
   - Done: both added.
5. Not blocking. The preflight put the OpenAI key and the gcloud token on `curl` command lines, readable by other local processes while the call runs.
   - Done: both headers go in on standard input (`curl -H @-`).

---

## Phase 1: checks and rules

- [ ] `Resolver` interface, `FixtureResolver`, `LiveResolver` (TXT only, two seconds per query, eight per check, forty queries at most).
- [ ] SPF, DKIM and DMARC checks as in `docs/SPEC.md`, tests first.
- [ ] Domain-name validation with every refusal in the spec.
- [ ] Twelve seeded clients on `.example` domains with fixture zones and seeded sources, each with its cycle of days. Between them they produce every fix type and a healthy client.
- [ ] Rules engine and the fix list, each fix with its type, source tag and instruction.
- [ ] `make check-domain DOMAIN=<name>` prints the checks and fixes for a real domain.

**Gate:** `make check` exits 0. Every fix type has at least one fixture case that produces it and one that does not (the test names them; count shown). An SPF chain of eleven lookups and an include loop are both reported as over the limit. All twelve seeded clients produce the same output on two runs (hashes shown, equal). `make check-domain DOMAIN=example.com` returns real results (output pasted). Each of the eight refusals of the live-check input in the spec has a passing test (count shown: 8 of 8).

**Log:**

---

## Phase 2: the model and the evals

- [ ] `RiskModel` interface with `OpenAIRiskModel`, `RecordedRiskModel`, `FixtureRiskModel`.
- [ ] `prompts/risks-v1.md`; the structured-output schema; validation of model output; IDs built in code.
- [ ] A test that no worked example in a prompt shares a domain or an input hash with an eval case.
- [ ] The spend ledger: checked before every paid call at the most that call could cost; stops before the cap in `docs/STANDING.md`.
- [ ] Eval harness, `make eval`, `make eval-live`, `evals/results.json`, recordings under `evals/recordings/<prompt version>/`.
- [ ] One paid call that shows whether `temperature` is accepted with reasoning off; the answer and what the code does about it are in the log and in decision 0002.
- [ ] `make eval-live` on `gpt-6-luna`. If a bar is missed: up to three further prompt versions, then the same on `gpt-6.1-terra`; the numbers for each attempt are in the log.
- [ ] One real failure from these runs and its fix are written down for the README.

**Gate:** `make check` exits 0. `make eval-live` output, pasted, shows over three runs of twenty cases: coverage at least 0.80, precision at least 0.80, harmful exactly 0, stability at least 18 of 20. `make eval STRICT=1` on the committed recordings prints the same four scores and exits 0. Recorded spend is under the cap. If every measure is at its maximum on the first live run, the set is too easy: stop for the owner with proposed harder cases (they touch the labels).

**Log:**

---

## Phase 3: snapshots and the handled loop

- [ ] `SnapshotStore` interface, `MemoryStore`, `FirestoreStore`.
- [ ] `visible_risks(ranked, handled, today)`, tests first: suppression for thirty days, the cap of five, the next risk moving up.
- [ ] The daily-write transaction and the handled / reopen transaction, for the shared scope and a sandbox scope.
- [ ] Emulator tests: the race, idempotency, TTL fields present on sandbox and live-check documents.
- [ ] The worker's core as a function: checks, rules, model, snapshot; dry-run mode that writes nothing.
- [ ] A model failure or invalid output saves the snapshot with fixes and "risks unavailable".

**Gate:** `make check` exits 0, emulator tests included. The race test runs the click and the daily write concurrently 50 times and passes 50 of 50: the click is kept and the handled risk is not visible. A risk handled on day 0 is hidden on day 29 and visible on day 30 (test output shown). The worker run twice for one date leaves exactly 1 snapshot document for that client and date. A dry run leaves 0 documents.

**Log:**

---

## Phase 4: schedule, worker, API, first backend deploy

- [ ] `/internal/dispatch` and `/internal/worker/{client}` with OIDC verification; `TaskQueue` interface; tasks two seconds apart.
- [ ] `/api/*`: clients, snapshot, handled, reopen, live check; the proxy secret; the actor.
- [ ] Live-check limits in Firestore counters: five per address per ten minutes, 200 a day, a ten-minute cache.
- [ ] `Alerter` and the change alert, tested against a fake; `NullAlerter` when no webhook is set.
- [ ] `make record` (paid): recordings for every state of every seeded client. A test fails if any seeded state has no recording.
- [ ] `make infra` and `make deploy-backend`: Cloud Run (at most one instance), Firestore with TTL policies, the queue with its retry settings, the Scheduler job, two service accounts, secrets, a budget alert of $5 a month.
- [ ] `make seed`, then one scheduled run triggered by hand.
- [ ] `docs/DESIGN.md`: the direction, the tokens, the list of screens and states. Written before Phase 5 starts.

**Gate:** `make check` exits 0. In CI, the six worker-auth cases pass: a valid token gets 200; a missing token, a wrong audience, a wrong service account, an expired token and a bad signature each get 401. Ten live checks fired at once from one address give at most 5 successes. With the day's counter set to 200, the next check is refused. On the deployed service, shown with pasted commands and output: `gcloud run services describe` reports a maximum of 1 instance; an unauthenticated call to the worker gets 401; one run of the Scheduler job leaves 12 snapshot documents dated today; a second run leaves 12; a live check of `example.com` through the API returns real DNS results; the budget exists. `docs/DESIGN.md` exists.

**Log:**

---

## Phase 5: the screens

- [ ] Server routes that proxy to the backend, the visitor session, admin sign-in and sign-out.
- [ ] Client list; client page with fixes above risks, handled and reopen, seeded labels, snapshot facts (date, prompt version, recorded); live check; eval table; about this demo.
- [ ] States, each reachable from seeded data or a query flag: loading, healthy with nothing to do, fixes only, risks only, both, a handled risk with the next one moved up, everything handled, risks unavailable, no snapshot today, live check running, live check result, live check refused, rate limited, daily cap reached, backend unreachable (fallback), admin signed in, sign-in refused.
- [ ] `make fallback` and the bundled fallback, with a test that it is current.
- [ ] `make screens`: screenshots of every state, light and dark, 1440 and 390 wide, into `docs/screens/`.
- [ ] Deployed to Vercel from `main`; checked in a real browser.

**Gate:** `make check` exits 0. `make screens` writes 4 screenshots for each of the 17 states (68 files; count shown). The verifier has looked at all of them and reports no state missing, no text below 4.5:1 contrast (computed), no horizontal scroll at 390 wide, and no control without a focus style. After merge, in a real browser on the Vercel URL with no key: the client list loads with 12 clients; a handled click on one client hides that risk and survives a reload; a second browser profile does not see that click; a typed `example.com` returns checks. With the backend URL pointed at nothing in a preview deployment, the page loads the fallback and shows the notice.

**Log:**

---

## Phase 6: report, README, release checks

- [ ] The report: HTML and Markdown, four sections (authentication, reputation, sending, actions), from a snapshot; a button on the client page.
- [ ] `README.md` on the seven-section spine in `docs/profiles/portfolio-piece.md`. Section 4 has the eval table generated from `evals/results.json`, the date, and one real failure and its fix. Section 6 is this build as it happened: run-through mode, the merge gate, which phases the owner merged, and the numbers from `docs/RUN_LOG.md`. A test fails if the table and the results file differ.
- [ ] The reviewer in security mode over the whole repository; every finding fixed or listed.
- [ ] A scan of the tree and the full history for real company and person names and for the client; the method and the result are in the log. The owner holds the name list: see `docs/STANDING.md`.
- [ ] `docs/VIDEO.md`: the walkthrough script for the owner, in the order the spec gives.
- [ ] Every "Done when" line in `docs/SPEC.md` checked and shown.

**Gate:** `make check` exits 0. `make eval STRICT=1` exits 0. The reviewer finds no sentence in the README that the code or the result files do not back (its list is in the log, with 0 open). The security review has 0 open blocking findings. `gitleaks git` over the full history reports 0 leaks. The name scan reports 0 hits. After merge: CI is green on `main`; the hosted page loads in a real browser in both themes at 1440 and 390 wide; the report opens for one client in both formats.

**Log:**

<!-- Every phase log ends with these three lines once the checks have run, one per line, starting at the
left margin, naming the commit each check was run on. The merge gate reads the last of each in this file.
    reviewer-verdict: no blocking findings @ <commit>
    verifier-verdict: pass @ <commit>
    challenger-verdict: no change @ <commit>
The verifier and the challenger may read "not needed @ <commit>" when the step list at the top of
the phase log said so and why, before the work began, where the reviewer could check it.
-->
