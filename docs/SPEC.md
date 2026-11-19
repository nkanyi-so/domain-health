# Spec: domain-health

## Claim

> A daily email-domain health check for many clients: clear-cut fixes from rules, judgment-call risks from a model, a human handled loop, and an eval harness for the model's list.

That sentence is the claim. It is kept in `docs/CLAIM.md` and a test pins it wherever it appears (README, the page, the report). Changing it is the owner's call.

**The honest paragraph** (README section 1, and in short on the page): a public rebuild of a deliverability monitor built for a client's internal platform. What is real: the DNS authentication checks (SPF, DKIM, DMARC) on any domain a visitor types. What is seeded: the twelve clients, their mailbox-provider reputation, blocklist status and sending statistics, because those come from accounts the demo does not have. The seeded clients' DNS answers come from a fixture resolver, and their model output on the hosted demo is recorded from real model runs, not generated on each visit. Seeded sources are labelled on the page.

## Who it is for and the problem

The reader is a recruiter or an engineering lead with two minutes. They should see a product a company would ship, try one real thing (type a domain), try the human loop (tick a risk handled), and find the evidence (the eval table) without being told where to look.

The problem it rebuilds: someone checks each client's sending domain by hand, across DNS tools and provider dashboards, and writes up what to fix. It is slow, it is skipped on busy days, and the write-up mixes two different things: faults with one correct fix, and risks that need judgment. The rebuild runs daily per client and keeps the two apart: rules produce the fixes, a model ranks the risks, and a person marks risks handled.

## In scope (by phase)

**Phase 0: scaffold, process layer and the measure.** Two toolchains behind one `make check`; CI with `check`, `secrets` and `eval` jobs; the labelling rubric, the forty labelled eval snapshots (thirty table cases and ten open cases), the bars and the claim pin, so the owner signs off the measure once.

**Phase 1: checks and rules.**
- A resolver interface with a live implementation (real DNS, TXT lookups only) and a fixture implementation (zone data in the repository).
- Checks: SPF present, single, syntactically valid, lookup count against the limit of ten, `+all`; DKIM probe over a fixed list of common selectors, key length; DMARC present, valid, policy, subdomain policy, percentage.
- Seeded sources for twelve invented clients on reserved domains (`.example`): reputation grade and its previous value, complaint rate, bounce rate, sending volume, open-rate trend, blocklist status and history, domain age. Each client has a small fixed cycle of days so consecutive days can differ.
- Rules engine: check results and seeded data in, a fix list out. Each fix has a type, a source tag (`dns` or `seeded`) and a plain-language instruction. No model.

**Phase 2: the model and the evals.**
- One model interface. The live implementation calls OpenAI with structured outputs. The model ranks up to eight risks from a closed list of risk types defined in `evals/RUBRIC.md`.
- A risk's ID is `<risk type>:<domain>`, built in code. Model output is validated before use: known type, no duplicates, at most eight, every number in its text present in its input.
- The prompt is a versioned file. Recordings of live output are stored per prompt version.
- The eval harness, `make eval`, `make eval-live`, the spend ledger, the results file.

**Phase 3: snapshots and the handled loop.**
- A store interface over Firestore: one snapshot document per client per day.
- Handled and reopen: a handled risk is suppressed for thirty days; the visible list is the first five ranked risks not suppressed; the next risk moves up.
- The daily write and the handled click are transactions over the same documents, so a click made during a run is never lost and a handled risk never reappears.
- Two scopes for the same code: the shared state (admin) and a per-visitor sandbox that expires after a day.
- Rerunning a day overwrites that day's document and never duplicates.

**Phase 4: schedule, worker, API, first backend deploy.**
- Dispatch endpoint: one Cloud Task per client, staggered. Worker endpoint: checks, rules, model (recorded), snapshot. Both accept only Google-signed OIDC tokens from the project's own service account. Dry-run mode.
- Public API behind the frontend's server routes: clients, a client's snapshot, handled, reopen, the live check.
- Live check for a typed domain: real DNS checks and the fix list only. No model call, no key. Rate limited and capped per day.
- Change alert: a Slack webhook message when a deterministic check differs from yesterday's. Built and tested against a fake; off on the hosted demo.
- Backend deployed to Cloud Run with Cloud Scheduler and Cloud Tasks, with the guards in "Surviving production".
- `docs/DESIGN.md`: the design direction, written before any screen.

**Phase 5: the screens.**
- Client list, client page (fixes above risks, handled and reopen, seeded labels, snapshot facts), the live check, admin sign-in, the eval table, an "about this demo" note.
- Light and dark, desktop and phone width. Every state has seeded data that shows it.
- Frontend on Vercel. If the backend cannot be reached, the page shows the bundled last-known snapshots and says so.

**Phase 6: report, README, release checks.**
- A client-ready report on demand, as HTML and Markdown, with four sections: authentication, reputation, sending, actions.
- README on the seven-section spine. Security review. A scan of the tree and the history for real names. The hosted demo checked in a real browser.

## Out of scope

Real mailbox-provider APIs. A real CRM. Multi-tenant accounts. A Google Doc export. A live model call on the hosted demo. Risks for a typed domain (it has no reputation or sending data, and the page says so). Email sending of any kind.

## How we know it works

### What is checked exactly (code, in `make check`)

- Every check and rule against fixture zones: one case per fix type, plus healthy.
- SPF lookup counting on nested includes, including a loop and a chain of eleven.
- Stable IDs: the same input gives the same IDs; the ID never comes from model text.
- Model output validation: an unknown type, a duplicate, a ninth item or an invented number is rejected.
- Only a case's `input` reaches the model: never its label, its note or its file name.
- No recording for a seeded client names a risk type the rubric's bands call wrong for that input.
- Suppression: handled today, hidden for thirty days, back on day thirty-one; the cap of five; the next risk moving up.
- The race: a handled click and a daily write run concurrently against the Firestore emulator; afterwards the click is kept and the handled risk is not visible.
- Idempotency: the worker run twice for one day leaves one document.
- Worker auth: a valid token is accepted; a missing token, a wrong audience, a wrong service account, an expired token and a bad signature are each refused with 401.
- The live check refuses anything that is not a public domain name, and stops at the rate limit and the daily cap.
- The eval code's own tests, and one run of the eval plumbing on fixtures with no threshold in it.
- The claim's wording wherever it appears. The README's eval table equals the results file.
- No worked example in the prompt comes from an eval case.

### The eval plan (the model's list)

**The set.** Forty labelled snapshots in `evals/cases/`, healthy and unhealthy mixed, in two sets (decision 0010):

- Thirty **table** cases. The label is exactly what the bands in `evals/RUBRIC.md` give, and a test re-derives it. At least six are built to be hard (signals that conflict, values near a threshold, a healthy domain that looks odd). A table of thresholds with no model scores full marks on these, so they show that the model follows the rubric, not that it judges.
- Ten **open** cases. The bands do not settle them: the label is a written call that departs from the bands, with its reason and, where one applies, the public guidance behind it. They are held out of prompt work: whoever writes or changes a prompt does not read them, and only their totals are reported.

Each case is the exact input the model receives, plus a label: `expected` (risk types a specialist would flag), `acceptable` (types that are not wrong to include), `wrong` (types that would be wrong or damaging to flag here). Any type in none of the three lists is noise. Every risk type is expected in at least two cases.

**Where the labels come from.** Drafted by AI against `evals/RUBRIC.md` and public deliverability guidance; the open cases by an agent that never sees the prompt. Reviewed and signed off by the owner, the engineer who built the original system, at the Phase 0 merge. Not written or reviewed by a deliverability specialist, and the README says so.

**No judge.** Risk types are a closed list, so every score is computed in code from IDs. The wording the model writes for a risk is not scored.

**The measures**, each over three live runs of all forty cases:

| Measure | Definition | Bar |
|---|---|---|
| coverage | expected risks found in the first five returned, divided by expected risks, summed over the cases; the mean of the three runs | at least 0.80 |
| precision | of the first five returned, those that are `expected` or `acceptable`, divided by the number returned, summed over the cases; the mean of the three runs. A case that returns nothing adds nothing | at least 0.80 |
| harmful | returned risks whose type is in the case's `wrong` list, counted over everything returned (up to eight, because a handled click moves the sixth to eighth into view) and over all three runs | exactly 0 |
| stability | the share of cases whose set of first five IDs is identical in all three runs | at least 0.90 |

Output that fails validation is **dropped**: for coverage it found nothing; for stability it never matches another run; and the number of dropped outputs is printed beside the four measures. "Harmful 0" is stated wherever it appears as "0 in 120 case-runs": it bounds the rate, it does not show never. Precision adds little on this set, because few label slots are noise; it is kept and that is said.

The bars live in `evals/bars.toml` and are judged on all forty cases together.

**Also reported, with no bar:** coverage for each risk type; every measure for the table set and for the open set separately; and beside each, the same measure for the **rules-only baseline**, which is the rubric's bands applied by code (`backend/src/domain_health/evals/table.py`), with no model.

**The model against the baseline.** On the table cases the baseline is perfect by construction, and the model can at best equal it. The open cases are where a model can show judgment. The model does better than the baseline there when, over the three runs, its coverage and its precision on the open set are each at least the baseline's, at least one of the two is higher, and its harmful count is no higher. If it does not, the claim's words "judgment-call" are not shown: the build stops for the owner and proposes the wording "judgment-call risks picked by a model from a closed list and scored against a written rubric".

**Rules for the paid runs.**
- The numbers that count at a gate are those of one run of the final prompt version. Every attempt, of every version, is reported with its numbers.
- An unchanged prompt is never run again to get a pass.
- A prompt does not quote the rubric's thresholds or bands, and no worked example in it comes from an eval case. Tests enforce both.
- Prompt changes are argued from table-case results only. Open-case results are looked at as totals, never case by case.

**Where each check lives.**
- `make check`: the eval code's tests and one fixture run of the plumbing. No threshold. Also here: the test that re-derives every table label and every fix list from the rubric, the test that an open label departs from the bands, and the validators that refuse an input that cannot happen.
- `make eval`: free. Scores the committed recordings for the current prompt version, writes `evals/results.json`, prints one line per measure with the score, the bar and `met` or `missed`, then the lines that have no bar. Exits 0 whenever it ran; with `STRICT=1` it exits non-zero on a missed bar, or when a prompt version exists with no recordings that match it and the cases. Before any prompt exists it prints "no prompt yet: nothing to measure" and exits 0.
- `make eval-live`: paid. Three runs of the forty cases through the live model, behind the ledger, writing the recordings and the same results file. All four bars need this run.
- CI: `make eval STRICT=1` in a job named `eval`, not a required check.
- Whether a bar is met is the challenger's reading of the pasted output at the phase gate.

**Gating a change.** A prompt change is a new version file. It ships only with recordings for that version that meet all four bars. The README's eval table names the prompt version, the model and the date.

**If the first live run scores full marks on everything,** the set is too easy: harder cases are added until something fails, the fix is made, and the before and after are kept. That touches the labels, so the owner merges that phase.

### What must be refused

- The live check: an IP address, a single label, a name longer than 253 characters, a reserved or internal name, anything with a scheme, path or port; a sixth check from one address in ten minutes; any check after the day's cap.
- The worker and dispatch endpoints: any caller without a valid Google OIDC token for the project's invoker service account.
- The public API: any call without the frontend's proxy secret. Shared-state handled and reopen: any call without an admin session.
- The model: output that fails validation is dropped, the client's snapshot is saved with fixes and a "risks unavailable" state, and the failure is logged.

## Surviving production

- **Schedule.** Cloud Scheduler, once a day, calls dispatch; dispatch enqueues one Cloud Task per client, two seconds apart; one failure does not block the rest.
- **Retries.** The queue retries a failed task with backoff, at most five attempts. DNS lookups time out at two seconds each and eight seconds per check.
- **Idempotency.** A snapshot's document ID is the date. A rerun overwrites.
- **Dry run.** The worker can run everything and write nothing, printing what it would write.
- **Cost and latency.** Each model call logs tokens, cost and latency. The paid eval and recording runs sit behind a ledger that stops before a call that could pass the cap. The hosted demo makes no paid call.
- **Limits on the public path.** Live check: five per address per ten minutes, 200 per day in total, at most forty DNS queries per check, results cached for ten minutes per domain.
- **Spend exposure.** Cloud Run with at most one instance, scaling to zero; a monthly budget alert on the project; no model key in production.
- **Secrets.** The proxy secret, the session secret and the admin passphrase live in Secret Manager and Vercel's environment. `.env.example` only in the repository.
- **Auth.** OIDC on the worker and dispatch, exercised in CI. Admin sign-in for shared state. Visitors get an anonymous signed session for their sandbox.
- **Staying up.** If the backend is unreachable the frontend serves bundled snapshots with a notice, so the page loads with no backend at all.

## Done when

- A real domain typed on the hosted page gets live DNS checks and a fix list.
- After one scheduled run, all twelve seeded clients have today's snapshot in Firestore.
- The eval table is in the README with the prompt version, the model and the date, and all four bars are met.
- CI is green on `main`. No key in the repository or its history. No real client, company or person in the story, the seeded data, the eval inputs or the history. The tools and hosts the project runs on, and the public guidance documents its eval labels cite, are named as what they are.
- The hosted page loads in a real browser with no key on the visitor's side, in both themes, at desktop and phone width.
- Left to the owner: the walkthrough video, and making the repository public.
