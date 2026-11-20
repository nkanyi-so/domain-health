# domain-health

A daily health check for the email sending domains of many clients. Rules produce the fixes a client is told to make. A language model picks judgment-call risks from a closed list, and the page shows those beside the fixes as advisory.

**The finding.** The eval was built before the prompt. It showed that a table of rules beats the model on this task: the table meets all four bars and no prompt version did. The product ships that way. The rules drive the action list. The model's risks sit beside it, marked advisory and unproven, never above a rules finding, with a link to the eval result.

> **The claim.** A daily email-domain health check for many clients: clear-cut fixes from rules, judgment-call risks picked by a model from a closed list and scored against a written rubric, a human handled loop, and an eval harness for the model's list.
>
> **Its limit.** On this project's evals a table of rules does better on the risk list than the model: it meets all four bars over the forty-eight cases and no prompt version did (on the thirty table cases the labels are that table's own output; on the eighteen open cases, in each of the three runs, the model found one more expected risk than the table, 18 of 25 against 17, and returned three wrong ones to its none).

**Hosted demo:** <https://domain-health-rose.vercel.app>. No key and no account are needed.

**This is a rebuild on synthetic data.** It is a public rebuild of a deliverability monitor built for a client's internal platform.

| Real | Seeded |
|---|---|
| The DNS checks (SPF, DKIM, DMARC) on any domain a visitor types: real lookups, TXT records only. | The twelve clients. They are invented companies on `.example` domains. |
| The schedule: Cloud Scheduler calls the service once a day, one Cloud Task runs per client, and each writes that day's snapshot to Firestore. | Their figures: reputation grade, complaint and bounce rates, sending volume, open rate, blocklist status, domain age. They would come from accounts the demo does not have. |
| The deployed services: the backend on Cloud Run, the frontend on Vercel. | Their DNS answers, which come from zone files in the repository through a fixture resolver. |
| The eval runs: five paid runs of a live model, 144 calls each, with every answer committed. | Their model output on the hosted demo. It was recorded from real model runs (`risks-v3` on `gpt-6.1-terra`, recorded 2026-11-20) and is replayed. Production holds no model key and makes no model call. |

A domain a visitor types gets the DNS checks and the fix list only. It gets no risks, because it has no reputation or sending data.

![A client page: the fixes first, the model's risks beside them as advisory](docs/screens/05-both-light-1440.png)

More screens: [a live check's result](docs/screens/11-check-result-light-1440.png), [a risk marked handled, at phone width in the dark theme](docs/screens/06-handled-one-dark-390.png), and all 68 in [`docs/screens/`](docs/screens/README.md). The walkthrough script is [`docs/VIDEO.md`](docs/VIDEO.md).

Sections: [1 Run it](#1-run-it) · [2 Before](#2-before) · [3 Decisions](#3-decisions) · [4 Evals](#4-evals) · [5 Surviving production](#5-surviving-production) · [6 How this was built](#6-how-this-was-built) · [7 What I'd do next](#7-what-id-do-next)

## 1. Run it

The quickest way is the hosted demo above. Type a domain to run the real DNS checks. Open a client and mark a risk handled: a visitor's ticks go to a sandbox of their own that expires after a day. The eval table is at `/evals`.

Each client page has an "Open report" button: a four-section report (authentication, reputation, sending, actions) as a page to print, with a Markdown download, for example [`/clients/northwind-cycles/report`](https://domain-health-rose.vercel.app/clients/northwind-cycles/report) after Phase 6 is merged. In it, as on the page, the fixes come first and the model's risks follow, marked advisory and unproven.

To run it locally you need `uv`, `pnpm`, Node 24 and, for the Firestore emulator, a JDK of 21 or later. No key is needed for any command below.

```bash
make setup                           # install both toolchains, enable the pre-commit hook
make dev                             # backend on the Firestore emulator, frontend on http://localhost:3000
make check                           # format, lint, types and tests for backend/ and frontend/, emulator tests included
make eval                            # free: scores the committed recordings, writes evals/results.json
make eval STRICT=1                   # the same, and exits non-zero because the harmful bar is missed
make check-domain DOMAIN=example.com # real DNS checks and the fix list for one domain
make readme                          # rewrites the generated tables in this file
make screens                         # the 68 screenshots in docs/screens/, with contrast, scroll and focus checks
```

`make eval-live` and `make record` call the live model and cost money. `make infra`, `make deploy-backend` and `make seed` write to Google Cloud. None of them is needed to run or check the project.

## 2. Before

Someone checks each client's sending domain by hand, across DNS tools and provider dashboards, and writes up what to fix. It is slow, and it is skipped on busy days. The write-up also mixes two different things: faults with one correct fix, and risks that need judgment. This rebuild runs daily for every client and keeps the two apart. Rules produce the fixes. A model ranks risks from a closed list. A person marks a risk handled, and it stays hidden for thirty days.

## 3. Decisions

Each record in [`docs/decisions/`](docs/decisions/) says what forced the choice, what was chosen and what it costs.

| Decision | Record |
|---|---|
| Rules produce the fixes. The model ranks risks from a closed list. Code builds each risk's ID as `<type>:<domain>`, so "handled" still means something the next day. | [0001](docs/decisions/0001-rules-and-model.md) |
| OpenAI structured outputs, reasoning off, temperature 0. The model was `gpt-6-luna` until the evals measured it; it is `gpt-6.1-terra` now. | [0002](docs/decisions/0002-model.md) |
| One model interface. The hosted demo replays recorded output. A typed domain gets no model call. | [0003](docs/decisions/0003-model-seam-and-recordings.md) |
| Firestore, one snapshot per client per day. The daily write and the handled click are transactions over the same documents. A visitor gets a sandbox. | [0004](docs/decisions/0004-firestore-and-the-handled-loop.md) |
| Backend on Cloud Run with Cloud Scheduler and Cloud Tasks, guarded. Frontend on Vercel with a bundled fallback. | [0005](docs/decisions/0005-hosting.md) |
| Backend stack: Python 3.14, FastAPI, uv, dnspython. | [0006](docs/decisions/0006-backend-stack.md) |
| Frontend stack: Next.js 16, TypeScript strict, Tailwind 4, pnpm. | [0007](docs/decisions/0007-frontend-stack.md) |
| Evals scored in code against four bars, with no judge. The measure was signed off before any prompt existed. | [0008](docs/decisions/0008-evals.md) |
| Auth: Google OIDC for the machine routes, a proxy secret for the API, an admin session, a visitor sandbox. | [0009](docs/decisions/0009-auth.md) |
| Two sets of eval cases, a rules-only baseline beside the model, tighter definitions. | [0010](docs/decisions/0010-measure-after-the-challenge.md) |
| Six objections to the rubric that were not taken. They are limits of the measure. | [0011](docs/decisions/0011-rubric-objections-not-taken.md) |
| The claim says what is measured. The comparison with the baseline is evidence, not proof. | [0012](docs/decisions/0012-the-claim-says-what-is-measured.md) |
| This README leads with the finding, then "Run it". | [0013](docs/decisions/0013-readme-leads-with-the-finding.md) |
| The Cloud Run service is opened by turning off the platform's invoker check, because the organisation policy refused the usual grant. | [0014](docs/decisions/0014-the-service-is-opened-by-turning-off-the-invoker-check.md) |
| Why each runtime dependency is there. | [dependencies](docs/decisions/dependencies.md) |

Smaller calls the build made by itself are in [`docs/DECISIONS_TO_REVIEW.md`](docs/DECISIONS_TO_REVIEW.md), each with how to undo it.

## 4. Evals

**The evals do not show that the model beats rules. They show the opposite: on these cases a table of rules does better than the model.** The model's risk list missed a bar, and the owner chose to ship the miss and say so.

### The table

Forty-eight labelled cases, three live runs of each, scored in code from risk types. There is no judge. The four bars are in [`evals/bars.toml`](evals/bars.toml) and are judged on all forty-eight cases together. This table is written by `make readme` from [`evals/results.json`](evals/results.json), the file `make eval` writes. A test fails if the two differ.

<!-- eval-table:start -->
Prompt in use: `risks-v3` (sha256 `11e24baa36aa`). Model: `gpt-6.1-terra`, reasoning effort `none`, temperature 0. Run recorded 2026-11-19: 3 runs of 48 cases, 144 case-runs. Outputs dropped by validation: 0 of 144.

| | coverage (bar: at least 0.80) | precision (bar: at least 0.80) | harmful (bar: exactly 0) | stability (bar: at least 0.90) | All four bars met |
|---|---|---|---|---|---|
| Model, prompt in use: `risks-v3` | 0.896, met | 0.962, met | **9 in 144 case-runs, missed** | 0.979 (47 of 48 cases), met | **no: harmful missed** |
| Rules-only baseline: the rubric's bands as code, no model | 0.881, met | 1.000, met | 0 in 144 case-runs (48 cases, 3 runs whose first five agreed on 48), met | 1.000 (48 of 48 cases), met | yes |
| Model, not in use: `risks-v4`, same model | 0.881, met | 0.940, met | **12 in 144 case-runs, missed** | **0.812 (39 of 48 cases), missed** | **no: harmful and stability missed** |
<!-- eval-table:end -->

What the measures mean (the exact definitions are in [`docs/SPEC.md`](docs/SPEC.md)):

- **coverage**: of the risks a case expects, the share found in the first five returned.
- **precision**: of the first five returned, the share the label calls expected or acceptable. It adds little on the table cases, because few label slots there are noise. It is kept anyway.
- **harmful**: returned risks the label calls wrong for that case, counted over everything returned (up to eight) and over all three runs. A harmful answer tells a client to worry about something that is fine.
- **stability**: the share of cases whose first five risks are the same in all three runs.

The rules-only baseline is the rubric's bands applied by code ([`backend/src/domain_health/evals/table.py`](backend/src/domain_health/evals/table.py)), with no model. Its row is scored by the same harness. Its zero is a count over 144 case-runs: it bounds a rate, it does not show never, and three runs of the same code are one sample, not three.

### What is missed, in plain words

- The harmful bar is missed. The bar is exactly 0. Version 3, the prompt in use, returned 9 in 144 case-runs: three wrong risks in each run, the same three each time, all on the open cases.
- No prompt version met all four bars. The rule "a prompt ships only with recordings that meet all four bars" is not satisfied by any version. The owner chose to ship the miss as it stands (2026-11-19).
- `make eval STRICT=1` exits non-zero on the harmful bar. CI's `eval` job runs `make eval EXPECTED=1` and is green only because [`evals/expected-misses.toml`](evals/expected-misses.toml) names that bar as a miss the owner chose to ship. A miss not named there turns the job red, and so does a named bar that is now met.
- The model did not do better than the rules-only baseline on the open cases in any attempt.

### Each set by itself

The cases come in two sets. In the thirty **table** cases the label is exactly what the rubric's bands give, so a table of thresholds scores full marks there by construction and the model can at best equal it. In the eighteen **open** cases the label is a written call that departs from the bands. The open cases were held out of prompt work: each prompt was written by an agent with fresh context that saw the rubric and the table cases only, and only the open set's totals are reported.

These numbers have no bar.

<!-- eval-sets:start -->
| Set | Who | coverage | precision | harmful answers | stability |
|---|---|---|---|---|---|
| table (30 cases, 42 expected risks) | model, `risks-v3` | 1.000 | 1.000 | 0 | 0.967 |
| | rules-only baseline | 1.000 | 1.000 | 0 | not in the results file |
| | model, only the types the bands expect kept | 1.000 | 1.000 | 0 | 1.000 |
| open (18 cases, 25 expected risks) | model, `risks-v3` | 0.720 | 0.900 | 9 | 1.000 |
| | rules-only baseline | 0.680 | 1.000 | 0 | not in the results file |
| | model, only the types the bands expect kept | 0.680 | 1.000 | 0 | 1.000 |

- Types `risks-v3` returned that the rubric's bands call merely acceptable, over the 3 runs: 22 on the table set and 30 on the open set. Types it returned that the bands call wrong: 0 and 0.
- The open set, run by run: the model found 18 of 25 expected risks in each of the 3 runs, the rules-only baseline 17. Harmful answers per run: the model 3, the baseline 0.
- Better than the rules-only baseline on the open set, by the four-part rule in `docs/SPEC.md`: **no**.
- Coverage by risk type, found/expected over the 3 runs: `dmarc_policy_none` 15/15, `dmarc_partial_enforcement` 9/9, `spf_near_lookup_limit` 9/9, `spf_weak_all` 6/6, `dkim_key_1024` 6/6, `reputation_declining` 21/21, `reputation_poor` 27/27, `complaint_rate_elevated` 18/18, `bounce_rate_elevated` 21/24, `volume_spike` 15/27, `new_domain_volume` 6/12, `engagement_declining` 12/12, `blocklist_recent` 15/15.
<!-- eval-sets:end -->

How to read this:

- **The model's list is the table's list plus merely-acceptable types.** Keep only the types the bands expect, and version 3's runs score exactly what the rules-only baseline scores on both sets. Everything else it returned is a type the bands call merely acceptable: 22 on the table set and 30 on the open set. Those extra types earned one more expected risk per run on the open set (18 against 17) and all nine harmful answers.
- **Coverage and precision are pooled.** They pass on forty-eight cases together. On the open set alone the model's coverage is 0.720 and the baseline's is 0.680, both under 0.80.
- **"All thirty table cases as labelled" needs its caveat.** On the table set version 3 found every expected risk in every run and returned nothing the label calls wrong. But the prompt restates the rubric's lines (see below), so this shows the model carrying out the rubric as the prompt restates it. It does not show the model following the rubric unaided.

### Version 3 is in use; version 4 was the final attempt

The prompt in use is version 3 (`risks-v3`), named by the `prompt` line in [`evals/settings.toml`](evals/settings.toml). It is the one the table above shows and the one the seeded clients are recorded with. Version 4 (`risks-v4`) was the final attempt. It did worse, and it is reported beside version 3 as not in use.

Version 4 was written to stop the model returning types the bands call merely acceptable. It was not a small change: it rewrote seven of the thirteen checklists, added a paragraph and a block of definitions, and is 457 words longer. It did stop those types. It also began raising a complaint-rate risk in about one call in seven, on cases whose complaint rate is a fifth of the level that matters. That gave ten wrong answers on the table cases, where version 3 has none, and nine cases that differ between runs.

**Why version 4 did worse is not established.** The same edit was made to two other checklists and did nothing of the kind. Between the two versions the harmful counts (twelve against nine) are within the noise of version 4's own runs. What is solid is the stability (39 stable cases against 47) and the ten wrong answers on the table cases against none.

### The wording a reader would have seen

- **Version 4, the final attempt: the wording was false.** In every one of its harmful answers the risk text said the complaint rate was "above the level mailbox providers recommend", on a rate a fifth of that level.
- **Version 3, the prompt in use: the wording was accurate and the call was wrong.** In its nine harmful answers the text describes the data correctly. The fault is that the risk was raised at all.
- **No check reads wording.** The evals score risk types only. The title and the reason a person reads are not scored.
- **A number written as a word is not checked.** Validation drops an output whose text holds a number the input does not hold, and it catches digits disguised with invisible characters, spaces or another script. It does not read "twelve" or "double", and it reads `900.000` as nine hundred. The prompt tells the model to write without digits, so in practice this rule sees very little.

One narrower check exists outside the evals: a test reads the seeded clients' recorded text and fails if it says a value is over one of the rubric's lines when the input is under it ([`backend/src/domain_health/seeded/recording_report.py`](backend/src/domain_health/seeded/recording_report.py)). It covers the twenty-six seeded states shown on the hosted demo, not the eval cases, and it cannot catch version 3's kind of harm, where the wording is true and the call is wrong.

### The Phase 2 result

Five paid attempts were made, on four prompt versions and two models. None met all four bars. The final attempt, version 4 on `gpt-6.1-terra`, scored coverage 0.881, precision 0.940, harmful 12 in 144 case-runs and stability 0.812: the harmful bar and the stability bar are missed. The best attempt, version 3 on the same model, scored 0.896, 0.962, 9 in 144 and 0.979 and missed the harmful bar alone. The rules-only baseline meets all four bars on the same cases. The owner set a limit of one further attempt after the fourth and chose to ship the miss as it stands (2026-11-19).

This table is scored again from the committed recordings by `make readme`. Costs are from the spend ledger, [`evals/ledger.jsonl`](evals/ledger.jsonl).

<!-- eval-attempts:start -->
| Attempt | Prompt | Model | Run on | coverage | precision | harmful answers (of 144 case-runs) | stability | dropped | Bars missed | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `risks-v1` | `gpt-6-luna` | 2026-11-19 | 0.552 | 0.986 | 2 | 0.792 (38 of 48 cases) | 0 | coverage, harmful, stability | $0.0563 |
| 2 | `risks-v2` | `gpt-6-luna` | 2026-11-19 | 0.816 | 0.841 | 24 | 0.667 (32 of 48 cases) | 1 | harmful, stability | $0.0757 |
| 3 | `risks-v3` | `gpt-6-luna` | 2026-11-19 | 0.786 | 0.877 | 20 | 0.688 (33 of 48 cases) | 0 | coverage, harmful, stability | $0.0787 |
| 4 | `risks-v3` | `gpt-6.1-terra` | 2026-11-19 | 0.896 | 0.962 | 9 | 0.979 (47 of 48 cases) | 0 | harmful | $0.7839 |
| 5 | `risks-v4` | `gpt-6.1-terra` | 2026-11-19 | 0.881 | 0.940 | 12 | 0.812 (39 of 48 cases) | 0 | harmful, stability | $0.8574 |
<!-- eval-attempts:end -->

Every attempt's full output is in the Phase 2 log in [`docs/PLAN.md`](docs/PLAN.md).

### One real failure and its fix

**"When in doubt, leave it out."** Version 1 closed with a blanket instruction to hold back, because one wrong risk fails a bar. On a small model with no reasoning step, that one sentence beat every description of when to raise a risk. Coverage was 0.552 (attempt 1), and a complaint rate under the hard limit was raised once in eighteen chances.

The fix was not a softer sentence. It was a different shape. Version 3 makes every risk type a short checklist: first the states in which it must never be raised, tied to named fields, then the condition for raising it. The fix list is the only word on whether a hard limit has been crossed. On the first model that was not enough (attempt 3: coverage 0.786, with three bars missed). On the model that could follow it (attempt 4), coverage is 0.896 and every expected risk on the thirty table cases is found in every run.

Two more failures from the same runs, both kept in the log:

- **Temperature 0 is not stability.** On `gpt-6-luna`, with reasoning off and temperature 0, three runs of the same input and the same prompt gave a different list in a fifth to a third of the cases, on three different prompts (attempts 1 to 3). A risk that comes and goes between runs would come and go between days, and "handled" would mean nothing. Stability was measured, and the measure is why the model changed. The cost is about ten times the price per run.
- **A prompt change that fixes one thing can unsettle another.** That is version 4, above. Only a full run on every case showed it.

### What the prompt says

A prompt may not quote the rubric's thresholds or bands, and a test enforces that. But the prompt in use does restate the rubric's lines relative to public limits that the model is asked to recall: "half that level or less", "a single lookup short of" the cap, "twice that length". The owner allowed this for version 3 because the limits are public (the SPF lookup cap, the complaint level mailbox providers publish), on condition that it is shown. `make eval` lists every such sentence in the results file, with no pass or fail. Here is the list.

<!-- prompt-wording:start -->
<details>
<summary>The 26 sentences of <code>risks-v3</code> that the results file lists</summary>

- Your list is exactly the types that came out as raise.
- Compare numbers exactly, place by place, without rounding either side.
- When there is not exactly a single valid record, `lookup_count` and `all_qualifier` are null because there is nothing to read; that null says nothing about the record's ending.
- `sources.blocklist`: `listed` (on a blocklist now), `listings_90d` (how many listings were active inside the lookback window, a current one included) and `days_since_delisted` (null while listed now, and null when no listing ended in the window).
- A value just short of a hard limit with no fix open is the most serious form of the risk, and it is yours to raise.
- The checklist names the figure; recall it, and compare the input value to it exactly.
- The figure: the large mailbox providers' bulk-sender guidelines give a complaint rate that senders are asked to stay under, and a second figure, several times larger, that must never be reached.
- A rate of half that level or less is the ordinary background of a healthy list, and naming it is plainly an error.
- `volume_7d` is only a few hundred messages or fewer, so that a single complaint could produce the whole rate: not raised.
- The figure: list-hygiene practice has a commonly quoted bounce rate that a clean list stays under, and providers act at a second level more than twice as high.
- Recall the bounce benchmark itself before you compare.
- A rate of half the benchmark or less is what most healthy senders show, and naming it is plainly an error, whatever the grade, the open rate or the fix list look like.
- `volume_7d` is only a few hundred messages or fewer, so that a handful of bounces could produce the whole rate: not raised.
- `volume_7d` is only a few hundred messages or fewer: not raised.
- Volume is flat, down, or has grown by only a fraction of the previous week's volume: not raised.
- Brisk growth that leaves the latest week short of a multiple of the week before is not a spike.
- The latest week is a multiple of the week before or more (reaching the smallest multiple exactly counts, and so does a week of sending after a week of none), the domain has years of history, and `grade` is `high`: not raised.
- Otherwise the latest week is a multiple of the week before, and either `grade` is anything other than `high` or the domain is too young to have a seasonal history of its own: raise.
- The domain is in its first few weeks and already sends real volume, thousands of messages a week: raise, alongside `volume_spike` when that was raised too; they are different risks.
- Recall the cap.
- There is not exactly a single SPF record, or `valid` is not true: not raised.
- `lookup_count` equals the cap exactly, or is a single lookup short of it: raise.
- For a count of half the cap or less, naming this is plainly an error.
- Current practice is a key of twice that length or more.
- Write without digits: "volume jumped several-fold", "opens lost a large share of their earlier level", "an older, shorter key", "at the lookup limit", "above the level mailbox providers recommend".
- If you must cite a figure, copy it exactly as the input holds it and cite nothing else.

</details>
<!-- prompt-wording:end -->

### Version 4's wording, boundary by boundary

Version 4 went a step past the owner's ruling on version 3. That ruling rested on the figures being public. Version 4 states no figure either, but it pins the rubric's lines at their exact boundaries through a field's name and plain spans of time, and neither of those is a public limit. The build let it run before asking. The reviewer said it should have gone to the owner first, and it should have. The owner then ruled that the attempt counts as the final attempt, with the wording disclosed. These sentences are taken from the results file's `not_in_use` list, grouped as [`docs/DECISIONS_TO_REVIEW.md`](docs/DECISIONS_TO_REVIEW.md) groups them.

<!-- v4-boundaries:start -->
- `dmarc_policy_none`, the rubric's 90 days:
  - The name of `listings_90d` gives its length in days.
  - `domain_age_days` is less than the length of the lookback window in days: not raised.
  - Otherwise `policy` is the value `none`, the domain is at least as old as the lookback window is long, and `fixes` holds nothing about SPF or DKIM: raise.
- `blocklist_recent`, the rubric's 30 days:
  - **A month**: exactly a third of the lookback window, counted in days.
  - A value equal to that count is "a month", not more and not less.
  - `days_since_delisted` is a month or less (a month as defined above; that exact count of days still fits): raise.
- `new_domain_volume`, the rubric's 30 days and its volume line:
  - `domain_age_days` has reached a month or more (a month as defined above): not raised, whatever the volume.
  - The domain is under a month old and `volume_7d` equals the bulk-sender count or is below it: not raised.
  - Otherwise the domain is under a month old and `volume_7d` is above the bulk-sender count: raise, alongside `volume_spike` when that was raised too; they are different risks.
- `volume_spike`, the rubric's 365 days:
  - The latest week is a multiple of the week before or more (reaching the smallest multiple exactly counts, and so does a week of sending after a week of none), the domain is a full year old or older (`domain_age_days` has reached the number of days in an ordinary year), and `grade` is `high`: not raised.
  - Otherwise the latest week is a multiple of the week before, and either `grade` is anything other than `high` or the domain is less than a full year old and so has no seasonal history of its own: raise.
- the low-volume line of `complaint_rate_elevated`, `bounce_rate_elevated` and `engagement_declining`, the rubric's 1,000 messages a week:
  - **Low volume**: `volume_7d` is in the hundreds or lower; it has not reached the thousands.
  - Low volume (`volume_7d` has not reached the thousands): not raised, whatever the rate is.
  - Low volume (`volume_7d` has not reached the thousands): not raised, however far the rate fell.
<!-- v4-boundaries:end -->

On the low-volume line version 3 said only "a few hundred messages or fewer". The whole list for version 4:

<!-- v4-wording:start -->
<details>
<summary>All 42 sentences of <code>risks-v4</code> that the results file lists under <code>not_in_use</code></summary>

- Your list is exactly the types that came out as raise.
- Compare numbers exactly, place by place, without rounding either side.
- A state that is only worth a passing remark comes out as not raised, exactly like a state that is fine: a young domain still in its monitoring period, a rate produced by a tiny week of sending, a single listing that ended long ago, a setup that is softer than the strictest and still does its job.
- When there is not exactly a single valid record, `lookup_count` and `all_qualifier` are null because there is nothing to read; that null says nothing about the record's ending.
- `sources.blocklist`: `listed` (on a blocklist now), `listings_90d` (how many listings were active inside the lookback window, a current one included) and `days_since_delisted` (null while listed now, and null when no listing ended in the window).
- A value just short of a hard limit with no fix open is the most serious form of the risk, and it is yours to raise.
- The checklist names the figure; recall it, and compare the input value to it exactly.
- **Low volume**: `volume_7d` is in the hundreds or lower; it has not reached the thousands.
- **The lookback window**: the span the blocklist fields look back over.
- The name of `listings_90d` gives its length in days.
- **A month**: exactly a third of the lookback window, counted in days.
- A value equal to that count is "a month", not more and not less.
- The figure: the large mailbox providers' bulk-sender guidelines give a complaint rate that senders are asked to stay under, and a second figure, several times larger, that must never be reached.
- Low volume (`volume_7d` has not reached the thousands): not raised, whatever the rate is.
- A rate of half that level or less is the ordinary background of a healthy list, and naming it is plainly an error.
- Otherwise the week's volume is in the thousands or more, the rate has reached the recommended level or is above it, by any margin, and no fix is open: raise.
- The figure: list-hygiene practice has a commonly quoted bounce rate that a clean list stays under, and providers act at a second level more than twice as high.
- Recall the bounce benchmark itself before you compare.
- A rate of half the benchmark or less is what most healthy senders show, and naming it is plainly an error, whatever the grade, the open rate or the fix list look like.
- Otherwise the week's volume is in the thousands or more, the rate has reached the benchmark or is above it, by any margin, and no fix is open: raise.
- Low volume (`volume_7d` has not reached the thousands): not raised, however far the rate fell.
- The week's volume is in the thousands or more and a substantial slice of the earlier rate has gone, a drop a specialist would call a change of level: raise.
- No listing ended in the lookback window.
- `days_since_delisted` is a month or less (a month as defined above; that exact count of days still fits): raise.
- Otherwise there was a single listing and it ended more than a month ago: not raised.
- Volume is flat, down, or has grown by only a fraction of the previous week's volume: not raised.
- Brisk growth that leaves the latest week short of a multiple of the week before is not a spike.
- The latest week is a multiple of the week before or more (reaching the smallest multiple exactly counts, and so does a week of sending after a week of none), the domain is a full year old or older (`domain_age_days` has reached the number of days in an ordinary year), and `grade` is `high`: not raised.
- Otherwise the latest week is a multiple of the week before, and either `grade` is anything other than `high` or the domain is less than a full year old and so has no seasonal history of its own: raise.
- Recall that count.
- `domain_age_days` has reached a month or more (a month as defined above): not raised, whatever the volume.
- The domain is under a month old and `volume_7d` equals the bulk-sender count or is below it: not raised.
- Otherwise the domain is under a month old and `volume_7d` is above the bulk-sender count: raise, alongside `volume_spike` when that was raised too; they are different risks.
- Recall the cap.
- There is not exactly a single SPF record, or `valid` is not true: not raised.
- `lookup_count` equals the cap exactly, or is a single lookup short of it: raise.
- For a count of half the cap or less, naming this is plainly an error.
- Current practice is a key of twice that length or more.
- `domain_age_days` is less than the length of the lookback window in days: not raised.
- Otherwise `policy` is the value `none`, the domain is at least as old as the lookback window is long, and `fixes` holds nothing about SPF or DKIM: raise.
- Write without digits: "volume jumped several-fold", "opens lost a large share of their earlier level", "an older, shorter key", "at the lookup limit", "above the level mailbox providers recommend".
- If you must cite a figure, copy it exactly as the input holds it and cite nothing else.

</details>
<!-- v4-wording:end -->

### Where the labels came from

The labels were drafted by AI against a written rubric ([`evals/RUBRIC.md`](evals/RUBRIC.md)) and public deliverability guidance: the bulk-sender requirements published by Google and by Yahoo, M3AAWG's sender best practices, and the SPF, DKIM and DMARC RFCs. The open cases were drafted by an agent that never saw a prompt. The labels were reviewed and signed off by the engineer who built the original system. **They were not written or reviewed by a deliverability specialist.** A specialist might disagree with some of them.

### Limits

**What was tried to show judgment, and why it fell short** ([decision 0012](docs/decisions/0012-the-claim-says-what-is-measured.md)). The claim first said "judgment-call risks from a model". Three rounds tried to build an eval that a model can pass and a table of thresholds cannot. Each time an independent challenger defeated it with no model:

1. Twenty cases labelled from the rubric's bands. About 130 lines of if/else reproduced every label.
2. Ten open cases were added, with a rules-only baseline scored beside the model. The baseline made to return one more band reached the pass mark with nothing harmful.
3. Eight harder open cases were added and two redrafted, with a four-part rule for "better than the baseline" and a test that no table which also returns the bands' acceptable types passes it. The test holds. But **a table with one number moved passes the comparison**: the baseline made to raise `volume_spike` from a ratio of 1.3, on any domain sending 1,000 messages a week or more, finds 21 of the 25 expected risks on the open set with nothing harmful, and meets all four bars with no model.

It kept falling short for one reason. Every label is a function of a small structured input: thirteen risk types and a dozen numeric fields. Any finite set of such calls can be matched by some table, and with eighteen open cases that table is a short one. Showing judgment this way would need inputs a table cannot key on, or labels from specialists on real domains. The project has neither. The owner set the limit before the third round, and the claim sentence was changed to say what is measured.

**The rules-only baseline alone meets the four bars**: coverage 0.88, precision 1.00, nothing harmful, the same answer every run. So meeting the bars would show agreement with a written rubric on synthetic cases, and no more. The comparison with the baseline is reported here as evidence. It is not a bar and the claim does not rest on it. What a model might add beyond a table (the wording a person reads, risks no table foresaw) is not measured here.

**The bands and the written calls are two standards, not one.** Six open calls make wrong a type the bands call acceptable. A prompt tuned on the table cases alone can therefore fail the harmful bar on calls it was never shown. That is a property of holding the open cases out, and it is what happened to version 3.

**The set is small.** Forty-eight cases, eighteen of them open. Three runs that agree are close to one sample, so the stability figure says little about stability across days or model updates.

**Six objections to the rubric that were not taken** ([decision 0011](docs/decisions/0011-rubric-objections-not-taken.md)). A second reader raised them "as a deliverability specialist would". The rubric stays as drafted on each, and a model that reasons like a specialist on these points can lose score against the labels:

1. Low volume is cut at 1,000 messages a week. Just above the cut, an "expected" complaint risk rests on very few complaints.
2. Low volume is a seven-day figure, but it also gates the thirty-day open rate.
3. A fall in open rate is given the same weight as the other signals, though mail privacy proxying inflates opens.
4. `p=quarantine` with `pct=0` counts as enforcing, though in effect it is `p=none`.
5. `volume_spike` and `new_domain_volume` can both be expected for one fact, so a new domain that ramps fast is counted twice.
6. A DKIM key found in DNS is treated as a key in use, though a key that answers at a selector is not proof that it signs mail.

## 5. Surviving production

What is deployed: a FastAPI service on Cloud Run with Cloud Scheduler, Cloud Tasks and Firestore, and a Next.js frontend on Vercel. The scripts are [`scripts/infra.sh`](scripts/infra.sh) and [`scripts/deploy-backend.sh`](scripts/deploy-backend.sh).

**The daily run.**

- Cloud Scheduler calls the dispatch route once a day (06:00 UTC). Dispatch enqueues one Cloud Task per client, two seconds apart. One client that cannot be enqueued does not block the rest.
- **Retries with backoff.** The queue tries a task at most five times (the first try and four retries), waiting from ten seconds up to five minutes between them. A DNS lookup times out at two seconds and a whole check at eight.
- **Idempotent.** A snapshot's document ID is the date, so a rerun overwrites and never duplicates. A test runs the worker twice for one day and finds one document.
- **The handled loop survives the run.** The daily write and the handled click are transactions over the same documents. A test runs them concurrently against the Firestore emulator; the click is kept and the handled risk stays hidden.
- **A dry run** does everything and writes nothing.
- If the model's output fails validation, the snapshot is saved with its fixes and "risks unavailable".

**Guards on spend and abuse.**

- **One instance at most**, and none when idle. The limit is set on the revision and on the service.
- **A $5 monthly budget alert.** It only alerts. No public request can make a model call, and the live check's lookups are capped. What a public request can cost is Firestore reads and Cloud Run time: one instance bounds their rate, nothing bounds their total, and the alert is what would catch a flood.
- **No model key in production.** The deployed service is built with the recorded model only. The `openai` package is in a dependency group the production image does not install, and a test walks the service's imports to hold that.
- **Live-check limits and a cache.** Five checks per address per ten minutes, 200 a day in total, at most forty DNS queries per check, and a result cached for ten minutes per domain. The counters are in Firestore, so they hold across restarts. The name is validated before any lookup: an IP address, a single label, a reserved or internal name, or anything with a scheme, path or port is refused.

**Auth.**

- **OIDC on the machine routes.** Dispatch and the worker accept only a Google-signed token for the service's own URL from the project's invoker account. The 401 cases are tests, run in CI with locally signed tokens: a valid token gets 200; a missing token, a wrong audience, a wrong service account, an expired token and a bad signature each get 401 ([`backend/tests/test_machine_routes.py`](backend/tests/test_machine_routes.py)).
- **The proxy secret.** Every `/api/*` route refuses a call without the secret shared with the frontend's server, so the limits cannot be skipped by calling Cloud Run directly. The service does not start with a secret shorter than 32 characters. The browser never sees it.
- Shared-state handled and reopen need an admin session. A visitor gets an anonymous signed session for a sandbox of their own.
- Secrets live in Secret Manager and Vercel's environment. Only `.env.example` is in the repository.

**Staying up.** If the backend cannot be reached, the frontend serves bundled snapshots of the twelve clients with a notice, so the page still loads with no backend at all. The live check then shows as unavailable.

**Real faults the deploy showed that no local test could.**

- **The first scheduled run answered 500, three times.** The Cloud Tasks client was made while the service was being imported, before the server's event loop existed, so its first use failed with "attached to a different loop". It needed the real client under the real server to show. The client is now made on the first enqueue, and a test holds that building the queue makes no client.
- **The organisation policy refused the grant that opens the service.** The design has the Cloud Run service open at the platform level, with every route refusing at the app level. The usual way to open it, granting `allUsers` the invoker role, was refused by the project's organisation policy. The service is opened by turning off Cloud Run's invoker check instead ([decision 0014](docs/decisions/0014-the-service-is-opened-by-turning-off-the-invoker-check.md)). The app's own checks are therefore the only gate, and the 401 an unauthenticated caller gets from the worker is the app's own.
- **The instance limit had two settings.** The deployed revision said one instance and the service said twenty. The reviewer would not accept a sentence that one of them wins. The deploy script now sets both to one.

Not on the hosted demo: the Slack change alert. It is built and tested against a fake, and no webhook is set.

## 6. How this was built

This was built by an AI coding agent (Claude Code) inside a harness, in phases, each on its own branch and pull request. The record is [`docs/PLAN.md`](docs/PLAN.md) (every phase's log, with the commands run and their output) and [`docs/RUN_LOG.md`](docs/RUN_LOG.md) (one line per event). The rules are in [`docs/harness/PRINCIPLES.md`](docs/harness/PRINCIPLES.md).

**Run-through mode.** The owner answered the standing questions once ([`docs/STANDING.md`](docs/STANDING.md)): who merges, the spend cap, what is irreversible, what may be public. After that the build merges its own phase, but only through a merge gate script. The gate merges when the independent checks have passed on the pushed commit, CI is green, nothing is waiting on the owner, and the diff touches neither the guards nor the files that state the claim or define the measure. Otherwise the pull request waits for the owner.

**Three independent checks.** The session that wrote the code does not approve it. Each check is an agent with fresh context:

- the **reviewer** reads the phase's diff against the spec and the plan;
- the **verifier** runs the software the way a user would;
- the **challenger** reads the claim against the way it is measured.

**The numbers**, counted from `docs/RUN_LOG.md` by `make readme`, for Phases 0 to 5. Phase 6 is the phase that adds the client report, this README, the security review and the release checks. Its row is still being written when this file is, so it is not counted here.

<!-- build-numbers:start -->
| Phase | Reviewer runs | Verifier runs | Challenger runs | Stops for the owner | Merge-gate refusals | Merged by |
|---|---|---|---|---|---|---|
| 0 | 12 | 3 | 6 | 3 | 0 | the owner |
| 1 | 12 | 1 | 0 | 0 | 0 | the merge gate |
| 2 | 11 | 2 | 2 | 2 | 0 | the owner |
| 3 | 4 | 1 | 1 | 1 | 0 | the owner |
| 4 | 4 | 2 | 0 | 2 | 2 | the merge gate |
| 5 | 4 | 2 | 1 | 1 | 0 | the owner |
| **Phases 0 to 5** | 47 | 11 | 10 | 9 | 2 | the merge gate 2, the owner 4 |
<!-- build-numbers:end -->

**Who merged what.** The merge gate merged Phases 1 and 4. The owner merged Phases 0, 2, 3 and 5:

- Phase 0 carries the guards and the whole measure, so it is always the owner's.
- Phase 2 was the checkpoint the owner set, and its gate was not met.
- Phase 3's challenger came back "change needed" on Phase 2's wording, and the answers changed CI and the list of measure files.
- Phase 5's challenger and verifier each found something, and the changes were the owner's to approve.

The two gate refusals in Phase 4 were not about the phase. One came seconds after a push, before the host showed the new commit. The other was a second line in the plan that began with the word "Spend:".

**What the checks caught.** One real example each, from the logs:

- **Reviewer, Phase 1.** The check that a typed name is a public domain let a trailing newline through, so a seeded name could have reached real DNS.
- **Reviewer, Phase 3.** A risk handled on yesterday's page showed again on today's snapshot, which breaks "a handled risk never reappears". Every read now computes the visible list from the marks.
- **Reviewer, Phase 5.** The admin sign-in limit could be passed by sending many wrong tries at once.
- **Verifier, Phase 4.** `make dev` did not start the backend: it crashed at start-up.
- **Verifier, Phase 5.** The page said every visitor sees the admin's ticks. They do not. The words were corrected.
- **Challenger, Phase 0.** Three times it wrote a table with no model that passed the measure. The claim sentence was changed as a result (decision 0012).
- **Challenger, Phase 2.** It traced version 3's nine harmful answers to the build's own brief to the prompt writers, which said an acceptable type "costs nothing".
- **Challenger, Phase 3.** It found that a line in this README's own checklist would have put a false sentence here: harmful written as a zero, when the result is nine.
- **Challenger, Phase 5.** One demo state showed risks recorded for other clients under the line "Recorded from a real model run". The page now says they were moved there.

**The build's own mistakes**, as the logs record them:

- A paid eval run went ahead past a failing test, because the two commands were joined in a way that did not stop on the failure. The test turned out to be the faulty part, but the run should not have started. The paid command now refuses a prompt that fails the check before its first call.
- Version 4's wording was let stand before a paid run without asking the owner.
- During the first deploy the build turned off an access setting on the live service to test something, before the owner had decided. It turned it back within minutes. The rule since: ask first.
- A command printed the proxy secret into the session's own output. It was never in the repository. It was replaced at once.
- A fix in Phase 5 was tried on the development server only and did not work in the production build. The next review caught it.
- Phase 1 took twelve review rounds. Most rounds found one more case of the same family, a malformed DNS record read as valid, where the class should have been fixed once.

**Cost of the process.** From Phase 3 on, the owner capped a phase at three review rounds before it stops. The first run-log line is 2026-11-19 14:05 UTC and Phase 5 merged on 2026-11-20 at 13:00 UTC.

**Spend.** $2.27 of the $10 cap, as of the Phase 6 pull request (the "Spend:" line in `docs/PLAN.md`). All of it is model calls in the ledger: the five eval attempts and one probe call on 2026-11-19, and the seeded clients' recordings on 2026-11-20. The ledger stops a paid command before a call that could pass the cap.

## 7. What I'd do next

- **Get labels from a deliverability specialist, on real domains.** That is the one thing that could change the finding. Until then the honest reading stays: on this evidence rules do as well on the risk list.
- **Give the model something a table cannot key on**, such as free text or history, before asking again whether it adds judgment.
- **More cases, not more runs.** Three runs at temperature 0 agree almost everywhere. Bounding the harmful rate near 2% would take about 150 distinct cases.
- **Run the same three runs on another day**, so the stability figure means stable across days and not only within one hour.
- **Read the wording.** Score the text a person reads, and check numbers written as words.
- **A sliding window for the per-address limit.** Today it is a fixed ten-minute window, so one address can make ten checks across a boundary. The daily cap still holds.
- **Real identity for the admin**, in place of one shared passphrase.
