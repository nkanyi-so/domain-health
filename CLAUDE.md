# domain-health

A daily email-domain health check for many clients, built as a public portfolio piece for a recruiter or engineering lead with two minutes. Real DNS checks (SPF, DKIM, DMARC) and seeded reputation and sending data become two lists: clear-cut fixes from rules, and judgment-call risks ranked by a model, with stable IDs, a handled / reopen loop, a daily per-client schedule and an eval harness for the model's list. The claim it has to prove is in `docs/CLAIM.md`.

Source of truth, in this order: `docs/SPEC.md` (what), `docs/ARCHITECTURE.md` (how), `docs/PLAN.md` (phases, gates, progress log), `docs/decisions/` (why). `docs/STANDING.md` holds the owner's standing answers (mode, spend cap, what is irreversible, what may be public); `docs/RUN_LOG.md` is the run's event log, written only through `bash .claude/hooks/run-log.sh` and the run-through scripts, and committed with the plan; `docs/harness/PRINCIPLES.md` holds the rules every project on this harness follows. If code and docs disagree, stop and say so. Files in `docs/profiles/`, if any, are rules for this project too.

## Commands

- `make setup` install dependencies for both toolchains, enable the pre-commit hook (`git config core.hooksPath .githooks`), warn if gitleaks or a JDK of 21 or later is missing
- `make dev` run the backend (against the Firestore emulator) and the frontend locally
- `make check` format check, lint, type check and tests for `backend/` and `frontend/`, emulator tests included. Must exit 0 before any commit.
- `make format FILE=<path>` format one file. The edit hook calls this; without the target nothing is formatted on edit.
- `make eval` free: scores the committed recordings, writes `evals/results.json` (the results file), prints one line per measure. `STRICT=1` exits non-zero on a missed bar.
- `make check-domain DOMAIN=<name>` real DNS checks for one domain. Free.
- `make screens` screenshots of every state into `docs/screens/`.
- `make fallback` regenerate the frontend's bundled snapshots.

Never run without being asked, or, in run-through mode, outside what `docs/PLAN.md` lists and `docs/STANDING.md` allows:

- `make eval-live` paid: three live runs of the forty cases.
- `make record` paid: records model output for the seeded clients.
- `make infra`, `make deploy-backend`, `make seed` write to Google Cloud. Always with the `domain-health` gcloud configuration (`CLOUDSDK_ACTIVE_CONFIG_NAME=domain-health`), never the machine's default one.

## Architecture rules

1. Every outside system sits behind its one interface in `docs/ARCHITECTURE.md` (`Resolver`, `RiskModel`, `SnapshotStore`, `TaskQueue`, `Alerter`, `Clock`). Nothing outside the implementation modules imports `dns`, `openai`, `google.cloud` or an HTTP client. A test checks the imports.
2. The model never decides identity or arithmetic. A risk's ID is built in code as `<type>:<domain>` from a type in the closed list; model output is validated before use and anything invalid is dropped, never repaired by hand.
3. The deployed service is built with `RecordedRiskModel` only. `openai` is in a dependency group the production image does not install, and no model key is ever set in Cloud Run or Vercel.
4. Every write of a snapshot or a handled mark goes through the two transaction functions in the store. No other code writes those documents, and `visible_risks` is the only place the visible list is computed.
5. Seeded clients resolve through `FixtureResolver` only. `LiveResolver` is reached only from the live-check path and `make check-domain`, and that path checks the rate limit and the daily cap before the first lookup.
6. No real company, person, client or platform name anywhere: code, fixtures, eval cases, docs, commit messages, branch names. Seeded domains end in `.example`. The story is "a client's internal platform".
7. The claim sentence, the eval cases, the rubric, the bars and the claim test (`.claude/hooks/measure-paths.txt`) are the owner's. A phase does not edit them; if one seems wrong, that is a stop.

## How phases are built

With `/next-phase`, which holds the working loop. If you are working on a phase without it, read `.claude/skills/next-phase/SKILL.md` first and follow it.

Who merges is set by `mode:` in `docs/STANDING.md`. In `gated` mode the human merges pull requests; you do not. In `run-through` mode you merge a phase only by running `bash .claude/hooks/merge-gate.sh <number>`, never with `gh pr merge` or any other way, and when it refuses, the pull request waits for the owner. You never edit `docs/STANDING.md` once it is filled in.

This file, `docs/SPEC.md`, the guards and the measure files are meant to be complete after Phase 0. A later phase that edits one is merged by the owner, so do not edit them for convenience: put what you learned in the phase log, `docs/ARCHITECTURE.md` or a decision record instead.

## Guardrails

- Never commit secrets. `.env` is ignored; only `.env.example` is tracked.
- No new direct runtime dependency without one line of reason in `docs/decisions/dependencies.md`.
- Never weaken a test, a check or a type check to make a gate pass. Say what is failing instead.
- Never call a live or paid service in tests or CI. Use a fake. That includes real DNS.
- Changes to `.claude/` (settings, hooks, agents, skills), `.githooks/` and CI must not weaken a check. In gated mode you will be asked to confirm each one; in run-through mode the owner merges any phase that contains one.
- When the build stops for the owner, it asks everything at once under "Waiting on you" in `docs/PLAN.md` and opens the issue with `bash .claude/hooks/stop.sh open`. A smaller call is made and recorded in `docs/DECISIONS_TO_REVIEW.md`.
- If a library's current API contradicts these docs, follow the library and note it in the phase log.
- If a gate cannot pass or the spec turns out wrong, stop and say so. Do not work around it.
- Design decisions are the build's, not the owner's: follow `docs/DESIGN.md`, do not ask about visuals, and have the verifier look at screenshots of every state in both themes and both widths.

## Style

- Backend: Python 3.14, type hints everywhere, `async` handlers, pydantic models for every request, response, stored document and model output. Ruff (format and lint), mypy strict, pytest. Dependencies through `uv`.
- Frontend: Next.js 16 App Router, TypeScript strict, explicit types on exported functions and props, ESLint, Prettier, Tailwind 4 with the tokens in `docs/DESIGN.md`. Node 24. Dependencies through `pnpm`.
- Small functions, plain names. Comments say why, not what. Plain words on the page and in the README.
