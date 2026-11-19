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
Decisions to review: 9 (`docs/DECISIONS_TO_REVIEW.md`)

Paid steps this plan lists (they run without asking while the worst case stays under the cap):

| Phase | Step | Worst case |
|---|---|---|
| 2 | one call to test whether `temperature` is accepted | $0.01 |
| 2 | `make eval-live`, up to six times on `gpt-6-luna` (120 calls each, after decision 0010) | $0.60 |
| 2 | `make eval-live`, up to four times on `gpt-6.1-terra`, only if Luna misses a bar | $4.00 |
| 4 | `make record` for every seeded client state, up to three times | $0.20 |
| 4 to 6 | Google Cloud outside the free tier (image storage, builds) | $1.00 |

Estimated total: under $6 (it was under $3.50 before the set went from twenty cases to forty). Everything else is free.

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

- [x] Project scaffold: `backend/` (Python 3.14, uv, ruff, mypy strict, pytest) and `frontend/` (Next.js 16, TypeScript strict, ESLint, Tailwind 4, pnpm), each with one real passing test.
- [x] `Makefile` with `setup` (installs both toolchains, runs `git config core.hooksPath .githooks`, warns if gitleaks is missing or no JDK of 21 or later is found), `dev`, `check` (both toolchains, emulator tests included), `format` (formats the one file passed as `FILE=`), `eval` (prints "no prompt yet: nothing to measure" until Phase 2), and stubs that fail with "not built yet" for `eval-live`, `record`, `seed`, `infra`, `deploy-backend`, `fallback`, `screens`.
- [x] Harness layer adapted to this stack: allow list in `.claude/settings.json` (never `eval-live`, `record`, `infra`, `deploy-backend`, `seed`), `protected-paths.txt`, `measure-paths.txt` corrected to the files that now exist, CI setup steps for both toolchains and the emulator, actions pinned by commit. List every change in the log.
- [x] CI has three jobs: `check`, `secrets`, and `eval` (runs `make eval STRICT=1`).
- [x] `.gitignore` (with `.env`), `.env.example` naming every variable from `docs/STANDING.md` and the deploy.
- [x] No `*.harness-new` file left: each one merged by hand and deleted.
- [x] `evals/RUBRIC.md`: the closed list of risk types (about twelve), each with when a specialist flags it, when it is acceptable and when it is wrong; the same for the line between a fix and a risk. A test asserts the code's list of types equals the rubric's.
- [x] `evals/cases/`: twenty labelled snapshots in the shape in `docs/ARCHITECTURE.md`, at least six hard, at least four healthy; every risk type expected in at least one case and wrong in at least one. A schema test loads all twenty. Labels second-read by a separate agent against the rubric; what it changed is in the log.
- [x] `evals/bars.toml` with the four bars from `docs/SPEC.md`.
- [x] `docs/CLAIM.md` and `backend/tests/test_claim_wording.py`, which checks the sentence in `README.md`, `frontend/src/content/claim.ts` and `backend/src/domain_health/report/templates/` wherever those exist.
- [x] `scripts/preflight-project.sh`, called by `.claude/hooks/preflight.sh`: confirms every owner action in `docs/STANDING.md` that a script can confirm (the OpenAI key answers for `gpt-6-luna`; the `domain-health` gcloud configuration exists, is signed in with a user account and points at `GCP_PROJECT_ID`; billing is enabled on that project; the login may create budgets; `vercel whoami` answers; Node 24 and a JDK of 21 or later are present). It reads names, never prints values.
- [x] Branch protection on `main`: no force-push, status checks required with this project's CI jobs picked as the required checks (`check`, `secrets`; not `eval`), and it applies to administrators too (a classic rule with "Do not allow bypassing", or a ruleset with an empty bypass list). The deny rules in settings are a courtesy; this is the guard. In run-through mode the merge gate checks it and merges nothing without it, so if it cannot be turned on, say so under "Waiting on you".
- [x] After the challenge (decision 0010, the owner's answers to issue #2): forty cases, thirty table and ten open; the open ten drafted by an agent that never sees the prompt; every risk type expected in at least two; `backend/src/domain_health/evals/table.py` (the rubric as a table, the rules-only baseline) with tests that re-derive every table label and fix list and that an open label departs from the bands; validators on the model's input; decisions 0010 and 0011.
- [x] `docs/STANDING.md` is filled in and lands on `main` with this phase. Every owner action in it is ticked or listed under "Waiting on you". `bash .claude/hooks/preflight.sh` output is in the log.

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

- `backend/`: uv project on Python 3.14; FastAPI app with `/healthz`; the two closed lists (`types.py`); the model's input (`models.py`); the eval case and its loader (`evals/cases.py`); `python -m domain_health.evals` behind `make eval`. Ruff, mypy strict (with the pydantic plugin), pytest. 41 tests, one of them marked `emulator`.
- `frontend/`: Next.js 16.4.6, React 19.3, TypeScript strict, ESLint (explicit types on exports are an error), Prettier, Tailwind 4.3, vitest. One page showing the claim; one test that the page's claim is the line in `docs/CLAIM.md`.
- `emulator/`: pinned `firebase-tools` 15.37.0 and `firebase.json`.
- `Makefile` and `scripts/` (`dev.sh`, `format-one.sh`, `toolchain-check.sh`, `preflight-project.sh`). `.gitignore`, `.env.example`.
- The measure: `evals/RUBRIC.md` (12 fix types, 13 risk types, the line between them), `evals/cases/` (20 cases: 9 hard, 7 healthy with nothing expected and no fix), `evals/bars.toml`, `docs/CLAIM.md`, `backend/tests/test_claim_wording.py`.

Changes to the harness layer, all of them (none removes or loosens a check):

- `.claude/settings.json`: five lines added to the allow list, each an exact command with no wildcard: `make eval`, `make eval STRICT=1`, `make dev`, `make screens`, `make fallback`. (Two more, `make format *` and `make check-domain *`, were in the first commit and were taken out after the review below.) Not added, so they always ask: `eval-live`, `record`, `infra`, `deploy-backend`, `seed`. Deny list and hooks unchanged.
- `.claude/hooks/protected-paths.txt`: four generated paths added (`evals/results.json`, `evals/recordings/*`, `frontend/src/data/fallback.json`, `docs/RUN_LOG.md`).
- `.claude/hooks/measure-paths.txt`: the five intake lines all name files that now exist; four added: `frontend/src/content/claim.test.ts`; after the second review `backend/src/domain_health/types.py` and `backend/tests/test_rubric_types.py`; after the third `backend/tests/paths.py`.
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
   - Not changed, by its own instruction and the working loop's: this is a question about the measure, so it is the owner's. It is true, and the build's own drafting confirms it: the labels were drafted by applying the rubric mechanically. The risk sentence above was written before the work and is left as written; the fact is that the context clauses are themselves fixed conditions on other fields. It goes to the owner as question 1 of the stop block that is written under "Waiting on you" once the verifier and the challenger have run. The reviewer's run is also a second reading of the five cases changed after the label check: "They all agree with the rubric as written."
4. Not blocking. `measure-paths.txt` did not list `backend/src/domain_health/types.py` or `backend/tests/test_rubric_types.py`, so a later phase could change the closed lists and the test that pins them together and be merged by the gate.
   - Done: both added.
5. Not blocking. The preflight put the OpenAI key and the gcloud token on `curl` command lines, readable by other local processes while the call runs.
   - Done: both headers go in on standard input (`curl -H @-`).

### 2026-11-19: review, third run, on ec5aa41

Verdict as reported: "one blocking finding, and it is a one-line doc fix. Everything else holds up, including the fixes from both earlier reviews."

1. Blocking. This log said of the mechanical-labels finding "It is question 1 under 'Waiting on you'" while that section still said "Nothing.": "no sentence in the log should name a block that does not exist". It also asked that the block carry the finding as the reviewer wrote it, the six objections not taken, the three decisions that set the measure, and the two missing owner values.
   - Done: the sentence now says where the question will go. The block is written at the stop, after the verifier and the challenger, and carries all four.
2. Not blocking. `backend/tests/paths.py` feeds the two protected tests their paths and was not itself protected.
   - Done: added to `measure-paths.txt`.
3. Not blocking. The newest prompt was picked by text order, so `risks-v9.md` would beat `risks-v10.md`.
   - Done: sorted by number, with a test; a file that is not exactly `risks-v<number>.md` is a stray and fails.

### 2026-11-19: review, fourth run, on 2e989a7

Verdict as reported: "no blocking findings." It checked the fixes from all three earlier reviews and the whole diff, ran the backend tests (40 passed, 1 deselected), `make eval` both ways and the preflight. One note, not blocking: the three decisions in `docs/DECISIONS_TO_REVIEW.md` that set the measure (input shape, type lists, the `spf_weak_all` change) are covered only because the owner merges this phase, and "that block must actually list them when the stop is written. If it does not, this becomes blocking." They are question 5 under "Waiting on you".

### 2026-11-19: verifier, on 2e989a7

| What it ran | Expected | What happened | Result |
|---|---|---|---|
| `make setup` | both toolchains installed, hooks path set, Node and JDK ok | hooks path is `.githooks`; printed `ok: Node 24`, `ok: JDK 23`; exit code not captured | pass |
| `make check` | exit 0, both toolchains, an emulator test | exit 0; `40 passed, 1 deselected`; emulator started and `1 passed, 40 deselected` ran inside it; frontend format, lint, typecheck, vitest (1 passed), `next build` | pass |
| `make format FILE=<a probe file>`; `make format` | formats the one file; usage error without FILE | `x=1` became `x = 1`; without FILE: `usage: make format FILE=<path>`, exit 2 | pass |
| `make eval`, `make eval STRICT=1` | "no prompt yet: nothing to measure", exit 0 | both printed it, exit 0 | pass |
| `make fallback`, `screens`, `check-domain` | "not built yet" | each printed `make <target>: not built yet`, exit 2 | pass |
| `make -n` with a paid or cloud target beside another goal (five pairs) | refused | each stopped with "is paid or writes to Google Cloud: run it alone, as the only goal" | pass |
| `make dev`, then both URLs | backend ok, page shows the claim | `/healthz` 200 `{"status":"ok"}`; the page holds the exact sentence from `docs/CLAIM.md` | pass |
| Stop `make dev` as Ctrl-C would | nothing left on 8000, 3000, 8085 | nothing left. (Its first try signalled only the parent, which left two processes; "That was my method, not the script's.") | pass |
| Commit with a deliberately failing test | refused | `FAILED tests/test_health.py::test_deliberate_break`, `1 failed, 40 passed`, "pre-commit: make check failed. Fix the cause before committing.", commit exit 1 | pass |
| Undo | tree as found | `git status` as at the start, HEAD still 2e989a7 | pass |
| `bash .claude/hooks/preflight.sh` | Node and JDK ok; the owner's two values missing | as expected; exit 1; "It cannot read [`preflight: ready`] today, because of the owner's missing variables." | pass for what was asked; the gate line is open |
| The case loader on a copy outside the repository | 20 load; broken cases refused | `loaded 20`; an unknown risk type and a case with missing fields were each refused with a validation error | pass |

Not exercised, in its words: a fresh-clone `make setup`; the page in a browser (HTML only was fetched); the paid stubs run alone; "the label quality of the twenty cases, which is a content review and not something to run."

### 2026-11-19: challenger, on 2e989a7

Its report, in its own words. Verdict: **change needed**. Nothing below has been acted on: it is the owner's to decide (question 1 to 4 under "Waiting on you").

**The bars.** "The Phase 0 gate has no eval bar. The four bars in evals/bars.toml are first judged at the Phase 2 gate." The pasted output and the code match; no results file exists, "consistent with the code, and the log says so"; "Bars met or missed this phase: not applicable, because there are no scores."

**1. Is the claim true as an absolute, or only for what the code can see?**

"The claim says 'judgment-call risks from a model … and an eval harness for the model's list.' Read at its widest: the model makes calls that need judgment, which a rule could not make; the harness shows that the list a reader sees is a good one."

"What passing all four bars would show. On these 20 hand-built synthetic inputs: in the first five types returned, the model finds at least 80% of the 27 expected types, pooled over cases; it never names a type from the rubric's `wrong` band in 60 case-runs; the same five-type set comes back three times in at least 18 cases. All of this is agreement with a decision table that the build drafted and the owner signs off."

"What it would not show:

1. Judgment. Every label and every fix list can be computed from the input. My script (about 130 lines read straight from evals/RUBRIC.md) reproduces all 260 label slots (20 cases × 13 types) and all 20 `input.fixes` lists exactly. [...] A rules engine with no model would score coverage 1.00, precision 1.00, harmful 0 and stability 20/20, which beats any model. Passing the bars therefore shows that the model follows a written table. It does not show 'judgment-call' risks. The risk sentence in PLAN.md ('The rubric keeps the judgment in the context clauses') is false: the context clauses are fixed conditions on other fields. By the project's own rule (docs/profiles/llm-app.md: 'Anything that can be computed … in code is'), these risks belong in rules unless the measure is changed.
2. What the reader reads. The model writes a title and a reason for each risk, and the reader sees them. Scoring looks only at the type. A right type with a wrong or alarming reason scores as perfect.
3. What the reader sees after a click. The model returns up to eight risks, and the visible list is the first five not suppressed. So positions 6-8 move up once a risk is marked handled. Harmful is scored on the first five only. A wrong type at position 6-8 is invisible to the measure but shown to the reader after one click on the handled loop the claim advertises.
4. Order. The spec says the model 'ranks', but order is not scored.
5. Every type. Coverage is pooled. Four types are expected in only one case each: `spf_near_lookup_limit` (case 10), `spf_weak_all` (12), `new_domain_volume` (16) and `blocklist_recent` (17). A model that never raises any of those four, and misses one more item, still scores 22/27 = 0.815 and meets the bar.
6. Dropped output. The spec does not say how output that fails validation is scored. [...] Under the precision definition, failing validation on an uncertain case costs no precision. It costs only coverage, and stability is undefined for it.
7. What the hosted demo shows. Visitors see recorded output for the 12 seeded clients. Those inputs are not the 20 eval cases and are never scored.
8. Who wrote the labels. An agent drafted them. [...] The five cases changed after the second read had only the reviewer's read since then.
9. The name 'harmful'. The `wrong` bands include harmless padding, for example `spf_near_lookup_limit` at 4 lookups, or `engagement_declining` on a 3% fall. 'Harmful 0' reads as 'said nothing damaging', but it means 'named no type outside its band in the first five, in 60 case-runs'."

"Wording that would be true under the measure as it stands: '…judgment-call risks picked by a model from a closed list and scored against a written rubric…' Alternatively, keep the wording and change the measure."

**2. Is the measurement too noisy to trust?**

"Coverage sits on a single item. The denominator is 27 per run, so each item is 0.037. Per run, 22/27 = 0.815 meets the bar and 21/27 = 0.778 misses it. Over three runs, 65/81 = 0.802 meets it and 64/81 = 0.790 misses it. If each item is hit independently at p = 0.8, one run has a standard deviation of about 0.077, and the mean of three about 0.044. That is larger than any likely margin over the bar, so a result like 0.81 has not cleared 0.80. Case 20 alone holds 5 of the 27 items (18.5%), and only 14 cases have any expected item. Uncertainty from which cases happen to be in the set is larger than the run-to-run noise, and more runs do not reduce it."

"Precision is in practice decided by the other two bars. Only 5 of the 260 label slots are noise: case 07 (2), case 15 (2) and case 16 (1). So with harmful at 0, at most 5 returns per run can be imprecise. [...] The precision bar adds almost nothing, and in this set 'noise' is not a real category."

"Harmful == 0 over 60 case-runs. With a true per-case-run rate of 1%, the chance of passing is 55%. At 2% it is 30%; at 5% it is 5%. Passing bounds the rate at about 5%. It does not show 'never'."

"Stability with temperature 0. [...] If that is accepted, three identical runs are likely, and stability then mostly measures the API's nondeterminism. [...] It also says nothing about stability when the input changes a little from day to day, which is what the handled loop depends on."

"Picking the best of several tries. PLAN.md budgets up to six `eval-live` runs on Luna. Prompt versions are tuned against the same 20 cases, with no held-out cases. Nothing says that re-running an unchanged prompt until it passes is forbidden. Nothing says whether the prompt may contain the rubric's thresholds. If it does, the eval measures how well the model follows a table."

"What more data costs. About $0.03 per 60-call Luna run. Five runs of the 20 cases: about $0.15. 60 cases × 3 runs: about $0.10, and labels are free, because [the script] produces them. [...] More cases do more than more runs."

**3. Could what the labels or a human caught be checked in code instead?**

"Yes, for every kind of fault found so far.

1. Label errors. The second read, three reviews and my own check all re-derived labels by hand. Check: a protected test that runs a code reading of RUBRIC.md and asserts every case's three lists. [...] It also makes the mechanical nature of the rubric visible.
2. Fix lists in case inputs. [...] Check now: a test that each case's fix types equal the fix table applied to its input. From Phase 1: equal to the rules engine's output on that input.
3. Unrealistic inputs. [...] models.py has no validators, so a case can break these rules silently. Pydantic validators on `SnapshotInput` could enforce: `open_rate_prev_pct` is null exactly when `domain_age_days` is under 60; listed now means `listings_90d` is at least 1 and `days_since_delisted` is null; `listings_90d` of 0 means `days_since_delisted` is null, and `days_since_delisted` is at most 90; the SPF fields `valid`, `lookup_count` and `all_qualifier` are null unless there is exactly one record; DMARC `policy`, `subdomain_policy` and `pct` are null unless the record is valid, and `pct` is set when it is.
4. Whether a case is hard. 'Hard:' is a note prefix the author sets. Code could confirm it: a case is hard if a small change to one field flips a label.
5. Wrong-band types at run time (the biggest). Because `wrong` is a function of the input, production code can drop any wrong-band type before it is shown, on every input, including the 12 seeded clients that visitors see and that are never scored. That makes harmful 0 by construction [...]. Short of a filter, a Phase 4 test can run every committed seeded-client recording through the same code and fail on any wrong-band type.
6. Inputs the model must not see. Code can check that only `input` reaches the model, never `note`, `label` or the file name."

**Its list of changes** ("each can be accepted or declined"):

- **A. Claim against the measure. Pick one.** "A1. Keep the wording and change the measure so it can show judgment: score a rules-only baseline with the same harness and report it beside the model; add about 10 cases labelled by the owner in which the rubric deliberately leaves the call open (labels that cannot be derived from a table); keep those cases out of prompt tuning. Cost: a few hours of the owner's labelling. A2. Reword the claim to what is measured, for example 'judgment-call risks picked by a model from a closed list and scored against a written rubric'. Cost: a weaker sentence. A3. Accept that rules can produce the list. Move the risk bands into rules (or a run-time filter) and give the model the order and the wording, then score those. Cost: a redesign of Phase 2 and probably the claim."
- **B. Score what the reader sees.** "Count harmful over all returned risks (up to eight), not just the first five. Cost: a definition change, no money. Optionally, report order agreement for positions 1-5."
- **C. Define invalid output in scoring.** "A dropped output counts as zero found for coverage. Report a 'dropped' count beside the four measures. In stability, a dropped run never matches another run."
- **D. Names and redundancy.** "Rename 'harmful' to 'outside the rubric', or split it into damaging and out-of-band. Require the README to say '0 in 60 case-runs'. Either accept that precision is effectively redundant here, or redraw the bands so that noise is a real category."
- **E. Coverage for each type.** "Report coverage per type, and have each type expected in at least 2-3 cases, or set a floor per type. Cost: about 10-20 more cases."
- **F. Noise rules.** "Raise the case count (preferred: about 60 cases, about $0.10 per three-run eval on Luna), or the runs. [...] Make the gate number the run of the final prompt version, report every attempt, and forbid re-running an unchanged prompt to pass. Keep a held-out split. Decide whether the prompt may quote the rubric's thresholds."
- **G. Checks in code.** "G1. A label-reproduction test (protected). G2. A fix-list test, now and against the Phase 1 rules engine. G3. Input validators on `SnapshotInput`. G4. A Phase 4 test that seeded-client recordings contain no wrong-band type, or the run-time filter in A3. G5. A test that only `input` is sent to the model. Cost: about a day of build work in total, and no money. G1 and G3 touch measure files and are owner-merged."

### 2026-11-19: gate evidence

The gate is **not ticked**. Four of its five parts are shown below; the fifth, `preflight: ready`, needs the owner's key and project. And the challenger's verdict is "change needed", which stops the phase whatever the gate says. The checklist boxes above are ticked because each artefact exists as the item describes it; the challenger's changes, if taken, change some of them again.

1. `make check` exits 0 with a passing test in each toolchain and the twenty cases loading (on 2e989a7; lines kept, the rest of the output is tool chatter):

```text
$ make check
15 files already formatted
All checks passed!
Success: no issues found in 15 source files
40 passed, 1 deselected in 0.18s
1 passed, 40 deselected in 0.13s
✔  Script exited successfully (code 0)
All matched files use Prettier code style!
 Test Files  1 passed (1)
      Tests  1 passed (1)
✓ Compiled successfully in 167ms
✓ Generating static pages using 4 workers (3/3) in 172ms
make check exit=0
```

`test_twenty_cases_load` is among the 40; the second line of counts is the test inside the Firestore emulator.

2. The pre-commit hook refuses a commit when a test is made to fail. The health test's expected body was changed to `{"status": "broken on purpose"}` and a commit attempted:

```text
$ git commit -m "this commit must be refused"
cd backend && uv run --frozen pytest -m "not emulator"
.................................F....                                   [100%]
>       assert response.json() == {"status": "broken on purpose"}
E       AssertionError: assert {'status': 'ok'} == {'status': 'b...n on purpose'}
FAILED tests/test_health.py::test_health_route_answers_ok - AssertionError: a...
1 failed, 37 passed, 1 deselected in 0.19s
make: *** [check-backend] Error 1
pre-commit: make check failed. Fix the cause before committing.
$ git log --oneline | head -1
9ac3c37 docs: blueprint from the intake (spec, architecture, plan, decisions, standing answers)
```

The line was put back before the first real commit. The verifier repeated the test on 2e989a7 with the same result.

3. CI ran green on the first push, all three jobs (commit 0a7b46b, run 44544363571), and on the commit the checks ran on:

```text
$ gh api repos/nkanyi-so/domain-health/commits/0a7b46b/check-runs -q '.check_runs[] | "\(.name)\t\(.conclusion)"'
secrets	success
check	success
eval	success
$ gh api repos/nkanyi-so/domain-health/commits/2e989a7/check-runs -q '.check_runs[] | "\(.name)\t\(.status)\t\(.conclusion)"'
check	completed	success
secrets	completed	success
eval	completed	success
```

4. Branch protection is on:

```text
$ gh api repos/nkanyi-so/domain-health/branches/main/protection -q '...'
required: check, secrets; strict: true; enforce_admins: true; allow_force_pushes: false; allow_deletions: false; required reviews: false
```

5. `bash .claude/hooks/preflight.sh` does not end with `preflight: ready` yet:

```text
$ bash .claude/hooks/preflight.sh
preflight on this machine, in /Users/nkanyisonzimande/Documents/GitHub/domain-health
ok:      git is installed
ok:      make is installed
ok:      python3 is installed
ok:      gh is installed
ok:      gitleaks is installed
ok:      the pre-commit hook is on
ok:      mode: run-through
ok:      owner: nkanyi-so
ok:      spend-cap-usd: 10
ok:      checkpoints: none
MISSING: OPENAI_API_KEY is not set. Owner: put it in .env or the shell, as the project's README says
MISSING: GCP_PROJECT_ID is not set. Owner: put it in .env or the shell, as the project's README says
ok:      measure-paths.txt names something
ok:      GitHub answers for nkanyi-so/domain-health over REST
ok:      this login can push to nkanyi-so/domain-health
ok:      the repository allows the 'merge' merge method
ok:      main is protected: status checks are required, administrators included (check, secrets). The merge gate also wants one of them to be a job of this project's CI
warning: docs/STANDING.md is not on main yet, so the merge gate treats the project as gated
ok:      Node 24
ok:      JDK 23
MISSING: the OpenAI key cannot be checked: OPENAI_API_KEY is not set
ok:      the gcloud configuration domain-health exists
ok:      the domain-health configuration is signed in with a user account
MISSING: the Google Cloud project cannot be checked: GCP_PROJECT_ID is not set
ok:      vercel whoami answers
warning: a script cannot confirm that Vercel's GitHub app can see this repository; the first deploy in Phase 5 will
ok:      the name list exists (not read here)
preflight: 4 thing(s) missing. Each MISSING line is a stop for the owner, asked once, together.
```

reviewer-verdict: no blocking findings @ 2e989a7
verifier-verdict: pass @ 2e989a7
challenger-verdict: change needed @ 2e989a7

### 2026-11-19: the stop (issue #2) and the owner's answers

The block as it was asked:

> **Phase 0 is built and waiting for you, for two reasons.** It is the phase you merge (pull request [#1](https://github.com/nkanyi-so/domain-health/pull/1)): it sets the guards and the measure. And the challenger, the independent agent that reads the measure against the claim, says a change is needed before you sign it off. Nothing has been changed in answer to it; the choices are yours. Everything else in the phase passed: the review (fourth run, no blocking findings), the verifier (every command works), CI (all three jobs green).
>
> **What the challenger found, in short.** Every label in the twenty cases can be computed from the input by about 130 lines of if/else read straight from `evals/RUBRIC.md`. Two independent agents wrote such a script and each reproduced all 260 label slots exactly. So a rules engine with no model would score full marks, and passing the four bars would show that the model follows a written table, not that it makes judgment calls. That is the word the claim leans on. Its full report, with eight more points about what the bars would not show and how noisy they are, is in the Phase 0 log below ("challenger, on 2e989a7").
>
> **1. The claim and the measure: which way do you want to go?**
>
> - **A1. Keep the sentence, make the measure able to show judgment (recommended).** You write about ten more cases where the rubric deliberately leaves the call open and only a specialist can label it: no table gives the answer. Those ten are kept out of prompt tuning. The harness also scores a rules-only baseline (the threshold script) and reports it beside the model. The README then says: on the table cases rules and model agree, and on the open cases here is what the model does that rules cannot. Costs you an hour or two of labelling; costs the build about half a day; no money beyond a cent or two per eval run. If the model does no better than the baseline on your ten, that is found in Phase 2 and you can still fall back to A2.
> - **A2. Keep the measure, reword the sentence** to what is measured, for example "judgment-call risks picked by a model from a closed list and scored against a written rubric". Costs nothing to build. A reader who asks "why is this not just rules?" gets no answer from the evals.
> - **A3. Move the risk bands into rules** and give the model only the order and the wording, then score those. This redesigns Phase 2, reverses decision 0001 and needs a judge for wording. Not recommended: it is a different project.
>
> **2. Tighter definitions for the four measures. Each is yes or no; I recommend yes to all four. They change `docs/SPEC.md`, which is why they are yours.**
>
> - **B.** Count "harmful" over everything the model returns (up to eight), not only the first five. Risks six to eight become visible as soon as someone ticks a risk handled.
> - **C.** Output that fails validation counts as nothing found for coverage, never matches another run for stability, and a "dropped" count is printed beside the four measures.
> - **D.** Keep the name "harmful", and have the README state it as "0 in 60 case-runs" (it bounds the rate at about 5%; it does not show never). Accept that precision adds little on this set.
> - **F (rules for the paid runs).** The number that counts at the Phase 2 gate is the run of the final prompt version; every attempt is reported; an unchanged prompt is never re-run to get a pass; the prompt may not quote the rubric's thresholds.
>
> **3. More cases?** Twenty cases hold 27 expected items, so one item is 0.037 of coverage and a score of 0.81 has not really cleared 0.80. Four risk types are expected in only one case each.
>
> - **Recommended: go to about forty**, with every type expected in at least two, and report coverage per type. With A1, your ten are part of the forty and I draft the other ten from the rubric for you to read. Costs you about fifteen more minutes of reading; about $0.02 more per paid run.
> - Or stay at twenty and have the README say how coarse the number is (decision 0008 already says so).
> - The stability bar "18 of 20" would have to be restated for a different count. Recommended: keep it as a share, at least 90% of cases.
>
> **4. Checks in code the challenger asked for (recommended: yes to all; no money, about a day across phases):** a protected test that re-derives every table-case label from the rubric, so a hand edit cannot drift; a test that each case's fix list is what the fix table gives; validators on the model's input so an impossible case cannot be written (for example an earlier open rate on a 40-day-old domain); in Phase 4, a test that no recording for a seeded client contains a type the rubric calls wrong there; a test that only a case's `input` reaches the model.
>
> **5. Sign off the measure as drafted, apart from the above.** Three things the build decided because it had to, all in `docs/DECISIONS_TO_REVIEW.md`: the shape of the model's input; the twelve fix types and thirteen risk types; and a change to `spf_weak_all` made after the second read (`~all` is only ever "acceptable"). And six objections from the second reader that were not taken, listed in the log under "second read of the labels": the low-volume cut at 1,000 a week, low volume gating the thirty-day open rate, how much weight an open-rate fall deserves, `p=quarantine; pct=0`, case 16 counting one fact twice, and DKIM keys that may not be in use. You are the specialist: say "as drafted" or correct `evals/RUBRIC.md` and the cases by hand in the pull request.
>
> **6. Owner actions still open in `docs/STANDING.md`** (the preflight lists the first two as MISSING; the commands are in that file):
>
> - The OpenAI key: `cp .env.example .env`, then set `OPENAI_API_KEY=`.
> - The Google Cloud project: the `domain-health` gcloud configuration already exists and is signed in; it still needs the project created, billing linked, and `GCP_PROJECT_ID=` in `.env`.
> - Vercel: `npm i -g vercel@latest`, and give Vercel's GitHub app access to this repository.
> - Then `bash .claude/hooks/preflight.sh` must end with `preflight: ready`.
>
> **What happens once you answer.** Answer in a comment on the issue or in the session. For whatever you accept in 1 to 4, I write a decision record and the proposed edit to `docs/SPEC.md` (and `docs/CLAIM.md` if you choose A2) on this branch, make the changes, and run the reviewer, the verifier and the challenger again on the result. You then read the measure and merge pull request #1; that merge is the sign-off. If you decline everything, say so and merge as it is: the challenger's verdict line stays as it gave it. Nothing in Phase 1 starts before the merge.

The owner's answers, given in the session, as written:

> 1. A1, with one change: I will not hand-label. Have an independent agent with fresh context, one that will never write, see or tune the prompt, draft the ten open cases. Each gets its label and a short reason, grounded in public deliverability guidance where it applies (Google and Yahoo sender requirements, M3AAWG). I review and sign them off at the merge. Keep those ten out of prompt tuning, and report the rules-only baseline beside the model. The README must state where the labels came from: drafted by AI against written guidance and reviewed by the engineer who built the original system, not by a deliverability specialist. If in Phase 2 the model does no better than the baseline on the open cases, propose the A2 wording and stop for me.
> 2. Yes to B, C, D and F.
> 3. Yes: about forty cases, every risk type expected in at least two, coverage reported per type, stability as a share of at least 90%.
> 4. Yes to all the checks in code.
> 5. As drafted. Record the six second-reader objections you did not take in a decision record, and name them in the README's limits.
> 6. Owner actions are done: .env has both values, the Google Cloud project exists with billing linked, the Vercel CLI is updated and its GitHub app has access. Run preflight to confirm. The name list is at ~/.config/domain-health/names.txt.
>
> Make my review at the merge quick: put a one-page table in the pull request description with each open case, the call, and the reason in one line, plus anything in the measure you are least sure of. Then run the reviewer, verifier and challenger again, and tell me when #1 is ready to merge. Do not ask me anything else unless the stop list requires it.

Preflight, run after the answers:

```text
$ bash .claude/hooks/preflight.sh | grep -vE "^ok:"
preflight on this machine, in /Users/nkanyisonzimande/Documents/GitHub/domain-health
warning: docs/STANDING.md is not on main yet, so the merge gate treats the project as gated
warning: a script cannot confirm that Vercel's GitHub app can see this repository; the first deploy in Phase 5 will
preflight: ready
```

Every other line was `ok:`, the OpenAI key for `gpt-6-luna`, the project, billing and the budget permission among them.

### 2026-11-19: after the answers, what changed

Docs first, as the owner's answers settle them: `docs/decisions/0010-measure-after-the-challenge.md`, `docs/decisions/0011-rubric-objections-not-taken.md`, the eval plan in `docs/SPEC.md`, the case shape in `docs/ARCHITECTURE.md`, `evals/bars.toml` (stability is a share, 0.90; the comments say what each bar counts), `docs/CLAIM.md` (what stands behind "judgment-call"), and "forty" for "twenty" in `CLAUDE.md`'s line for `make eval-live`. In this file: one checklist line added to Phase 0, one to Phase 2, a clause to one item in each of Phases 4 and 6, the Phase 2 gate reworded to the new measure, and the paid-steps table (a paid eval run is now 120 calls; worst case for the build under $6, cap $10). The Phase 2 gate is the one gate whose words changed; the owner merges this phase. `docs/STANDING.md` still shows the old estimate table and "twenty labelled cases": it is the owner's file and is not edited by the build.

Then the work:

- **Forty cases.** The twenty are kept (each gained `"set": "table"`). Ten more table cases, 21 to 30, drafted from the rubric by the build, bring every risk type to at least two expected cases. Ten open cases, 31 to 40.
- **The open cases were written by a separate agent** with fresh context, told that it will never write, see or tune the prompt, and to report back nothing about their content. This session has not opened the case files; it knows their file names, that the four kinds of departure from the bands are spread 3, 3, 2, 2, and that the agent "did not check the public guidance documents on the web. The notes cite them by name only, from memory, with no quotations or section numbers". The file names are descriptive and hint at each case's theme; that much has been seen. The summary table and the doubts go into the pull request description for the owner. They were meant to pass through unread, but this session saw both while assembling the description (the tool displayed the file). It has therefore seen one line about each open case. What follows from that is in decision 0010 and the decisions file: in Phase 2 the prompt is written by a fresh-context agent that gets the rubric and the table cases only.
- **`backend/src/domain_health/evals/table.py`**: the rubric read as a table (`fix_types`, `table_label`) and the rules-only baseline (`baseline_risks`).
- **Tests** (141 in the backend now, one of them in the emulator): every case's fix list is what the fix table gives; every table case's label is what the bands give; every open case's label departs from the bands and its note starts with "Open:"; forty files, ten of them open and named so; every type expected at least twice; fifteen inputs that cannot happen are each refused.
- **Validators** on the model's input: SPF, DMARC and blocklist fields have to agree with each other, and an earlier open rate exists exactly from 60 days of age.
- **`.claude/hooks/measure-paths.txt`**: six more lines, so a later phase that changes the input model, the case shape, the table reading or the tests on them is merged by the owner: `backend/src/domain_health/models.py`, `evals/cases.py`, `evals/table.py`, `tests/test_eval_cases.py`, `tests/test_rubric_table.py`, `tests/test_input_validation.py`.
- **Rubric**: where the labels come from; the two sets; a closing section "Open cases". Nothing in the bands changed.

The mix, counted by script without reading the open cases:

```text
table 30 open 10 hard 13 healthy 12 expected items 53 min per type 2 types 13
```

`make eval` after the changes:

```text
$ make eval
no prompt yet: nothing to measure
```

Still no results file: there is no prompt. The rules-only baseline and the per-type and per-set lines are printed by the harness Phase 2 builds.

### 2026-11-19: review, fifth run, on b2e056c (the first after the answers)

Verdict as reported: "blocking findings (5). Each one is cheap to fix. Most are things the owner has to confirm explicitly at the merge." It confirmed that the changes carry out the owner's answers, that `table.py` matches the rubric "band by band, including boundaries" with one exception (finding 2), that cases 21 to 30 are right against the rubric, and that SPEC, ARCHITECTURE, RUBRIC, `bars.toml`, CLAIM, the Phase 2 gate and the code agree. Its findings on the open cases were given to this session by number only; the detail went to a file this session has not read.

1. Blocking. "Owner-level changes the build made beyond the literal answers. Each needs the owner's explicit yes at the merge": the plan edits (the Phase 2 gate's wording, the added and extended checklist items), and the definition of "better than the baseline", which "changes the measure, so it should have been a stop".
   - Done: both are listed in the pull request description under "What you approve by merging", in plain words. They were not made a second stop: the owner's answers said to ask nothing more unless the stop list requires it, the owner merges this phase whatever it holds, and every one of these follows from an answer. The reviewer's point stands that a definition of the measure is the owner's, which is why it is put in front of them by name and not left in the decisions file.
2. Blocking. `table.py` treated a previous open rate of 0 as nothing to read; the rubric said that only of null.
   - Done: the rubric now says "null or 0" in both places, and a test covers it. No table case has such an input; the open case that did is finding 5.
3. Blocking. "Real organisation names in the tree" (the open-case notes, decision 0010, the decisions file, the quoted answers) against rule 6 in `CLAUDE.md`, `docs/STANDING.md` and the "Done when" line in the spec.
   - Done: the owner asked for the grounding by name, and the repository already names the tools and hosts it runs on, in `docs/STANDING.md` itself among others, so the rule was never literal. Rule 6 and the spec's "Done when" line now say so: no real client, company or person in the story, the seeded data, the eval inputs or the history; tools, hosts and cited public guidance documents are named as what they are. Both edits are in the list the owner approves by merging. `docs/STANDING.md` is not edited by the build; its sentence is about the story and the seeded clients.
4. Blocking. The pull request description was stale: "twenty cases", no open-case table, no list of doubts.
   - Done: rewritten (see the hand-over below).
5. Blocking for two cases. Open cases 39 and 40 blocking, 38 "should fix", 37 and 33 minor; 31, 32, 34, 35 and 36 "no finding".
   - Done by a second fresh agent, under the same rule as the first (it never sees the prompt and reports nothing about content): it fixed or replaced the five from the reviewer's file and rewrote the summary table and the doubts.

Not blocking: table case 28 gave a steady `high` grade to a domain with 0.29% complaints and 4.9% bounces. Done: the grade is `medium`, and `reputation_poor` moves from wrong to acceptable, as the bands give. The stale "twenty" in the ticked Phase 0 item and in the Phase 0 gate is left as written, because a run does not edit them: the evidence below shows forty loading. `docs/STANDING.md`'s estimate table and its "skim the twenty cases" are the owner's.

### 2026-11-19: review, sixth run, on 4c82fd0

Verdict as reported: "2 blocking findings. Both blocking findings are cheap to fix. Both are about what the owner is told before signing off; neither is a code defect." It found `table.py` and the rubric in agreement, all ten open cases sound and the earlier findings on 33, 37, 38, 39 and 40 resolved, table case 28 correct, and the pull request description's table, lists and counts accurate.

1. Blocking. "'Better than the baseline' quietly requires perfect precision on the open set." It scored the baseline on the ten open labels: "coverage 9/14, precision 12/12 and harmful 0", perfect precision "by construction", so "at least the baseline's" meant exactly 1.00 across thirty case-runs, and "one noise pick fails the claim test". The spec's "Precision adds little on this set" was false for this comparison, and neither list of doubts said any of it.
   - Done: the build's own definition was wrong and is changed to the reviewer's option (b): coverage higher than the baseline's, harmful no higher, precision at least the 0.80 bar. The spec, decision 0010, the decisions file and the pull request description say why, give the numbers (the model has to average at least 10 of 14 on the open set), and offer the owner the stricter alternatives. "Precision adds little" now says "on the table cases".
2. Blocking. The pull request description said rule 6 and the "Done when" line had both been reworded the same way; in fact rule 6 only gained a sentence, and the spec line had also dropped "in the tree". The decisions entry was stale.
   - Done: the spec line says "in the tree or the history" again, so both rules differ from before only by the one added sentence. The description quotes the sentence and says exactly that; the decisions entry and its undo steps are corrected. The description also now names the "twenty" to "forty" edit in `CLAUDE.md`.

Not blocking: open case 34's note attributed a line to both providers' requirements that is in one only. Done by a fresh agent, note only.

### 2026-11-19: review, seventh run, on c7874ae

Verdict as reported: "one blocking finding. It is cheap to fix, and like the sixth round's findings it is about what the owner is told, not a code defect." It recomputed the baseline: "Open set: coverage 9/14 (0.643), precision 12/12, harmful 0. Table set: 42/42, 42/42, 0." It found the three sixth-round fixes holding and SPEC, ARCHITECTURE, RUBRIC, `bars.toml`, CLAIM, the Phase 2 gate, decision 0010, `table.py` and the cases in agreement.

1. Blocking. "The '10 of 14' figure misstates the new rule": the spec required only coverage "higher" than the baseline's, the mean of three runs, so "runs scoring 9, 9 and 10 ... pass. So one extra expected item in one run of three is enough", "within run-to-run noise", while the owner was told "at least 10 of 14 on average".
   - Done, by making the rule what the owner was told, which is also the firmer of the two it offered: the model has to find on average at least one more expected item per run than the baseline, 30 of 42 as the cases stand. The spec, decision 0010, the decisions file and the pull request description now say the same thing with the same numbers. (The "Done" line under the sixth run above was written before this and reads "at least 10 of 14"; the rule is the one here.)

Worth noting, as it put it, and what was done:

- Decision 0010 still said precision adds little "on this set". Done: "on the table cases".
- The decisions entry on naming said nothing else in either rule changed; the spec line also gained "client,". Done.
- "Nothing guards the 1.00 precision premise." Done: a test fails if an open label moves a type the bands expect to wrong or to noise, and another if the baseline stops missing anything on the open cases.
- The pull request description said five review rounds. Done.
- "twenty cases" twice in the decisions file's input-shape entry. Done.
- "The measure changed through the decisions file, not a stop... I treat this as covered, not blocking: Phase 0 is owner-merged, and item 1 of the pull request asks for the owner's approval of that definition by name. The owner's merge must be read as that approval." Agreed, and said in the hand-over.
- The verifier and the challenger last ran on 2e989a7 and have to run again on the final commit. They do, next.

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
- [ ] From decision 0010: the harness scores the rules-only baseline beside the model, for the table set and the open set; prints coverage per risk type and the dropped count; counts harmful over everything returned. Tests: only a case's `input` reaches the model; a prompt quotes none of the rubric's thresholds. The prompt is written and changed by an agent with fresh context that is given the rubric and the table cases only; it does not read the open cases, the Phase 0 pull request's description or any per-case result on the open set.

**Gate:** `make check` exits 0. `make eval-live` output, pasted, shows over three runs of the forty cases: coverage at least 0.80, precision at least 0.80, harmful exactly 0 (over everything returned), stability at least 0.90 of the cases, with the dropped count, coverage per risk type, and the rules-only baseline beside the model for the table set and the open set. The numbers are those of one run of the final prompt version, and every attempt is in the log. On the open cases the model does better than the baseline as `docs/SPEC.md` defines it; if it does not, stop for the owner with the weaker claim wording proposed. `make eval STRICT=1` on the committed recordings prints the same four scores and exits 0. Recorded spend is under the cap. If every measure is at its maximum on the first live run, the set is too easy: stop for the owner with proposed harder cases (they touch the labels).

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
- [ ] `make record` (paid): recordings for every state of every seeded client. A test fails if any seeded state has no recording, or if a recording names a risk type the rubric's bands call wrong for that input (decision 0010).
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
- [ ] `README.md` on the seven-section spine in `docs/profiles/portfolio-piece.md`. Section 4 has the eval table generated from `evals/results.json`, the date, and one real failure and its fix. Section 6 is this build as it happened: run-through mode, the merge gate, which phases the owner merged, and the numbers from `docs/RUN_LOG.md`. A test fails if the table and the results file differ. The README also says where the labels came from (drafted by AI against written guidance, reviewed by the engineer who built the original system, not by a deliverability specialist), shows the rules-only baseline beside the model, writes harmful as "0 in 120 case-runs", and names the six limits in decision 0011.
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
