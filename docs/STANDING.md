# Standing answers: domain-health

Asked once, at the intake on 2026-11-19. The build reads this file instead of asking again. It is the owner's: once its mode line is set, the agent does not edit it, and the merge gate goes by the copy on the default branch. To change an answer, edit it by hand and merge that yourself.

The lines in this first block are read by scripts. Keep each as `key: value` on one line.

mode: run-through
owner: nkanyi-so
spend-cap-usd: 10
checkpoints: none
requires-env: OPENAI_API_KEY, GCP_PROJECT_ID

## Who merges

- `gated`: every phase stops at its open pull request and the owner merges it.
- `run-through`: after Phase 0, the run merges its own phase through `.claude/hooks/merge-gate.sh` and starts the next one. It stops only for the reasons under "What stops the run". Phase 0 and every checkpoint are merged by the owner in both modes.

This project is run-through. The owner merges Phase 0, which carries the guards, the commands and the whole measure (rubric, twenty labelled cases, bars, claim sentence), and then expects not to be needed.

## Checkpoints

None, by the owner's choice. The two default checkpoints (first working draft, first eval results) are switched off. What covers them instead: the measure is fixed and signed off in Phase 0 before any prompt exists; the challenger reads every eval result against the bars and answers the three questions; and a "change needed" from the challenger still stops the run for the owner. The screen phase is not a checkpoint and needs no mock approval: design decisions are the build's, recorded in `docs/DESIGN.md`, and the verifier looks at screenshots of every state in both themes and both widths.

## Spend

Cap: $10 for the whole build. The owner's Claude usage is not counted.

What is paid: OpenAI calls in Phase 2 (the eval runs) and Phase 4 (recording the seeded clients' output), and anything Google Cloud charges outside its free tier.

| Phase | Estimate, worst case |
|---|---|
| 0, 1, 3 | $0 |
| 2 | $2.31: one temperature test call ($0.01), up to six eval runs on `gpt-6-luna` ($0.30), up to four on `gpt-6.1-terra` if Luna misses a bar ($2.00) |
| 4 | $0.70: recording, up to three times ($0.20); image storage and builds ($0.50) |
| 5, 6 | $0.50: image storage and builds |
| Total | under $3.50 |

One eval run is 60 calls of about 2,000 tokens in and 600 out: about $0.03 on Luna, about $0.35 on Terra, counted here at $0.05 and $0.50.

Under the cap, a paid step that `docs/PLAN.md` lists runs without asking. A step that could take the total past the cap, counted at the most it could cost, is a stop. The ledger in the code enforces the same number before every paid call.

After the build, the hosted demo is expected to cost nothing to a few cents a month: no model key in production, Cloud Run limited to one instance and idle at zero, and the free tiers of Firestore, Cloud Tasks and Cloud Scheduler.

## Hosting

- **Backend:** Google Cloud, project named by `GCP_PROJECT_ID`, region `us-central1`: Cloud Run (at most one instance), Cloud Scheduler (one daily job), Cloud Tasks (one task per client), Firestore (Native mode), Secret Manager. Deployed by the run from the owner's machine with `make infra` and `make deploy-backend`, always through the `domain-health` gcloud configuration. A merge to `main` does not deploy the backend by itself.
- **Frontend:** Vercel, team `nkanyi-so`, project `domain-health`, root `frontend/`, connected to the repository. A merge to `main` deploys production.
- **Guards:** one instance at most; a $5 monthly budget alert; five live checks per address per ten minutes; 200 live checks a day; no model call on the hosted demo.
- **Fallback:** if the backend cannot be reached, the frontend serves bundled snapshots with a notice, so the page still loads. If outbound DNS over UDP does not work from Cloud Run, the live resolver uses TCP. If Cloud Run, Tasks or Scheduler cannot be made to work as planned, that is a stop, not a move to another host: they are part of the claim.
- **Where the build runs:** the owner's Mac only. It needs the gcloud login, the Vercel login and `.env`, none of which a cloud session has.

## What counts as irreversible

Always a stop, whatever the mode: deleting anything outside the working tree (a project on a host, a database, a branch someone else uses), rewriting published git history, sending anything to people, and anything on this project's own list:

- Creating the Firestore database fixes its location for good. This one is allowed in advance: Native mode, `us-central1`.
- Deleting the Google Cloud project, the Firestore database, or any document the run did not write. The run may delete and recreate only what it created itself in this project: service revisions, the queue, the scheduler job, seeded and test documents.
- Deleting or replacing a Vercel project, or touching any other Vercel project or Google Cloud project on this machine. In particular the machine's default gcloud configuration belongs to other work and is never used, changed or read.
- Rotating, revoking or deleting any of the owner's keys.
- Installing software on the machine outside the repository's own dependencies.

## What may be made public

Already public: nothing. The repository `nkanyi-so/domain-health` is private until the owner releases it.

The run may do these by itself:

- Push branches, open pull requests and stop issues on this repository, and merge through the merge gate.
- Enable the Google Cloud APIs it needs in the project named by `GCP_PROJECT_ID`, and run `make infra`, `make deploy-backend` and `make seed` there. The Cloud Run URL is public and is guarded as described above.
- Create the Vercel project `domain-health` in team `nkanyi-so`, connect it to the repository, set its environment variables, and deploy previews and production. The Vercel URL is public.
- Make real DNS lookups for domains used in checks, and call OpenAI as the plan lists.

Never alone: change the repository's visibility, add a custom domain, publish a package, post or announce anywhere, send a real Slack message, or record or upload the video.

Must never appear anywhere public, the git history, commit messages and branch names included: the real client, its platform, its people, its data or its terms. The story is "a client's internal platform". No real company and no real person, public figures included: seeded clients are invented companies on reserved domains such as `.example`. The only real domain names in the repository are ones reserved for documentation (`example.com`, `example.org`, `example.net`).

## Owner actions

Things only the owner can do, listed up front so the run does not discover them one at a time. Tick each when done. `bash .claude/hooks/preflight.sh` confirms every one a script can confirm; do all of them before merging Phase 0.

- [x] `gh` signed in as `nkanyi-so`. Checked at the intake.
- [x] Repository `nkanyi-so/domain-health` created, private. Done at the intake.
- [x] Branch protection on `main`: a classic rule requiring `check` and `secrets`, branch up to date, enforced for administrators, no required reviews, no force-push. `eval` is deliberately not required. Set at the intake over REST.
- [ ] **OpenAI key.** At platform.openai.com: create a project named `domain-health`, set its monthly budget to $10, make sure the account has at least $5 of credit, and create an API key in that project. Then in the repository folder: `cp .env.example .env` and set `OPENAI_API_KEY=` in `.env`. The key stays on this machine; it is never set in Cloud Run or Vercel.
- [ ] **Google Cloud project, on a personal Google account.** The gcloud on this machine is signed in to work accounts and its default project is a work project; none of that may be used. In a terminal, replacing `<id>` with a new project ID such as `domain-health-demo-` plus four digits, and `<billing>` with the ID from the list command:

  ```bash
  gcloud config configurations create domain-health --no-activate
  gcloud auth login --configuration=domain-health          # choose the personal account in the browser
  gcloud projects create <id> --name="domain-health" --configuration=domain-health
  gcloud config set project <id> --configuration=domain-health
  gcloud billing accounts list --configuration=domain-health
  gcloud billing projects link <id> --billing-account=<billing> --configuration=domain-health
  ```

  Then set `GCP_PROJECT_ID=<id>` in `.env`. If `gcloud billing accounts list` shows nothing, create a billing account first at console.cloud.google.com/billing with a personal card. It must be a full (paid) account, not the 90-day free trial: a trial stops everything when it ends. The project ID is public in the service URL, so it must not contain the client's name.
- [ ] **Vercel.** `vercel whoami` already answers on this machine for team `nkanyi-so`. Two steps: update the command-line tool with `npm i -g vercel@latest`, and give Vercel's GitHub app access to the repository: github.com/settings/installations, then Vercel, Configure, Repository access, add `domain-health`, Save. A script cannot confirm the second one; the first Vercel deploy in Phase 5 will.
- [ ] **The name list.** Create `~/.config/domain-health/names.txt`, outside the repository, one per line: the real client, its platform, its people, and any other real name that must never appear. Phase 6 scans the tree and the full history against it and reports only the number of hits. The file is never copied, committed or printed.
- [ ] **Read the measure, then merge Phase 0.** In the Phase 0 pull request, read `evals/RUBRIC.md`, skim the twenty cases in `evals/cases/` (about fifteen minutes), correct any label by hand, and check the sentence in `docs/CLAIM.md`. Run `bash .claude/hooks/preflight.sh`; it must end with `preflight: ready`. Then merge.
- [ ] **Start the run.** In the repository folder: `claude --permission-mode auto`, then `/next-phase`. The build pauses when the Mac sleeps; `caffeinate -dims` in another terminal keeps it awake.
- [ ] **After the build:** record the walkthrough from `docs/VIDEO.md`, then make the repository public. Branch protection stays as it is.

## What stops the run

1. A credential or another step only the owner can do.
2. Spend that could pass the cap.
3. Anything irreversible or outward-facing that is not listed above as allowed.
4. A gate that cannot pass after a real attempt.
5. A change to what the project claims or how it is measured, including any such change the challenger says is needed.
6. A checkpoint.
7. A phase whose diff touches the guards (settings, hooks, agents, the working loop, CI), `CLAUDE.md`, `docs/SPEC.md`, the files in `.claude/hooks/measure-paths.txt`, or a gate or checklist item already in `docs/PLAN.md`: the owner merges that one.

Known in advance for this project: if the first live eval run in Phase 2 scores full marks on every measure, harder cases have to be added, which touches the labels, so the owner merges that phase (items 5 and 7).

Anything smaller, the run decides and records in `docs/DECISIONS_TO_REVIEW.md`.
