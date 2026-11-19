# Decisions to review

Calls the run made without asking, because none of them was a reason to stop (see "What stops the run" in `docs/STANDING.md`). Newest first. The owner reads these when convenient and writes `kept` or `undo` in the Status line; an `undo` is done at the start of the next phase.

A decision belongs here when the run would otherwise have asked: a choice between workable options, a reading of an unclear line in the docs, a tighter rule than the one written. A change to the claim, the measure, spend past the cap, or anything irreversible or public does not belong here. That is a stop.

<!-- Copy this block for each decision.

## YYYY-MM-DD, Phase N: the decision in a few words

- **Decided:** what was chosen, and what the other option was.
- **Why:** the reason, with the evidence if there is any.
- **To undo:** the exact steps (the commit to revert, the setting to change back) and what undoing costs.
- **Status:** to review

-->

## 2026-11-19, Phase 1: the phase goes to `main` as one commit on a second branch

- **Decided:** the first three commits of this phase held, in two test files and one log line, a few domain names that are not documentation names (an invented company name under `.com`, a short `.co.uk` name, a one-letter `.com` name). None was ever looked up. They were replaced in the tree, but the merge gate merges with a merge commit, which would have carried those commits into `main`'s history for good. So the phase's work was put on a new branch, `phase-1-checks-and-rules-clean`, as a single commit made from `main`, and the pull request is opened from that branch. The first branch, `phase-1-checks-and-rules`, was not rewritten and not deleted: rewriting pushed history and deleting a branch are both the owner's. The other options were to merge the history as it was, or to stop and ask.
- **Why:** `docs/STANDING.md` says the only real domain names in the repository are the documentation ones, and history on `main` cannot be taken back without rewriting it. A new branch costs nothing and changes nothing that exists. The log lines for the first three reviews name commits (6d64db6, 6473c88, 041e969) that live only on the first branch.
- **What is left in history:** the one commit that starts this branch, 2e75ed2, has four test lines with garbled forms of "example" under `.com` (one with an umlaut, one built by a loop, one with a space in it, one with a tab); the next two commits move them under `example.org`. They are misspellings, not anyone's name, and the fourth review did not hold the merge for them, so the branch was not made a third time.
- **To undo:** nothing to undo on `main`. To finish the clean-up, delete the first branch before the repository is made public: `git push origin --delete phase-1-checks-and-rules`. Until then those three commits are reachable on GitHub, in a private repository.
- **Status:** to review

## 2026-11-19, Phase 1: "reserved" means the special-use endings, not the three documentation domains

- **Decided:** the live check refuses a name ending in `.example`, `.test`, `.invalid`, `.localhost`, `.onion` or `.alt` as reserved, and one ending in `.local`, `.internal`, `.lan`, `.home`, `.corp`, `.intranet`, `.localdomain`, `.private` or `.arpa` as internal. `example.com`, `example.net` and `example.org` are accepted. The other reading was to refuse those three as reserved too.
- **Why:** the Phase 1 gate and the spec's "Done when" both ask for real results for `example.com`, and those three zones do answer. A side effect that is wanted: a seeded client's `.example` domain typed into the live check is refused, so a seeded name can never reach real DNS.
- **To undo:** add the three names to `RESERVED_SUFFIXES` handling in `backend/src/domain_health/domain_name.py` and change the gate's domain, which is the owner's line.
- **Status:** to review

## 2026-11-19, Phase 1: a check that cannot be made is "unavailable", outside the model's input

- **Decided:** a lookup that does not answer, a check that passes eight seconds, or a domain past forty lookups makes that check unavailable, with the reason, and it gives no fix. A server failure counts as no answer. One DKIM selector that does not answer makes the whole DKIM check unavailable. The other options were to read silence as "no record" (wrong fixes), or to add an "unknown" state to the model's input (a change to the measure).
- **Why:** `SnapshotInput` has no field for it, and a missing-record fix issued because a server was slow is the worst thing this tool could say. Seeded clients resolve from fixtures that always answer, so their input is always whole. What the worker does if it ever meets an unavailable check is Phase 3's.
- **To undo:** nothing to revert without choosing one of the two other options; the second is an owner-merged change to `models.py` and the cases.
- **Status:** to review

## 2026-11-19, Phase 1: how SPF is read where the standard leaves room

- **Decided:** (1) Lookups are counted as the standard counts them (`include`, `a`, `mx`, `ptr`, `exists`, `redirect`), following includes and redirects as TXT lookups; `a`, `mx`, `ptr` and `exists` are counted and not resolved, so the separate limit on lookups that return nothing is not checked. (2) Counting stops when the limit is passed, so a loop, a chain of eleven and a chain of thirty all report 11. (3) An include or redirect whose target has no SPF record, several, or one that does not parse makes the record invalid (`spf_invalid`), as a receiver would treat it. (4) With no `all` of its own, a record that redirects takes its ending from the target. (5) A name with a macro in it is counted and not followed. (6) A term behind `all` is never reached by a receiver: it still has to parse, but it costs no lookup and is not followed. (7) A record is ASCII and its terms are separated by spaces; anything else does not parse. (8) Terms are held to the standard's grammar (RFC 7208, section 12): macros, prefix lengths with their ranges and no leading zero, addresses, a name ending in a top label with at most one trailing dot. One thing is stricter than the grammar: a name with no macro that DNS could not hold (an empty label, a label over 63 characters, a character outside letters, digits, hyphen and underscore) makes the record invalid in any term, because no receiver can use that term.
- **Why:** the resolver does TXT only by design, and a bounded walk is what keeps one domain under forty lookups. `lookup_count` only matters to the rules and the rubric as "eleven or more", "nine or ten", "eight", and five or fewer.
- **To undo:** each is a few lines in `backend/src/domain_health/checks/spf.py` with its test in `backend/tests/test_spf.py`.
- **Status:** to review

## 2026-11-19, Phase 1: how DKIM and DMARC are read where the standard leaves room

- **Decided:** DKIM: twelve generic selectors (`default`, `dkim`, `mail`, `email`, `smtp`, `selector1`, `selector2`, `s1`, `s2`, `k1`, `k2`, `key1`), none naming a company; a key's length is the RSA modulus read from the key; a revoked (empty) key is not a key; a key that is not RSA is found but has no `key_bits`, is never weak, and stops `dkim_missing`. DMARC: a name with no record inherits a parent's, looked for at up to four names (the name, its nearest parents, and always the two-label parent), and reports the policy that applies to the name asked about; a record with no `p=`, an unknown policy, a bad `pct`, or a second DMARC record does not parse. A record is DMARC only if it opens with the tag `v=DMARC1`, that exact value in either case; `v=DMARC10` is no DMARC record, so the fix is `dmarc_missing`. DMARC is deliberately not held to two of the standard's stricter lines, because receivers are not: `p=` does not have to be the second tag, and tags other than `p`, `sp` and `pct` are not checked. `pct` is one to three digits. A DKIM record's `v=`, when present, has to be its first tag. A space inside a DMARC value is part of the value, so `p=re ject` does not parse. A DKIM record of another version, of a key type that does not exist, with a key that does not decode (an Ed25519 key is 32 bytes), or marked as not for email, is not a key.
- **Why:** the selector list cannot be complete, which is why the fix says "or tell us the selector in use". `key_bits` is the only thing the input says about a key and it means RSA. The walk up follows the direction the standard has taken and keeps a typed subdomain from getting a false `dmarc_missing`.
- **To undo:** `SELECTORS` in `backend/src/domain_health/checks/dkim.py`; `MAX_NAMES_TRIED = 1` in `checks/dmarc.py` turns the walk off.
- **Status:** to review

## 2026-11-19, Phase 1: the twelve seeded clients and their days

- **Decided:** twelve invented companies, each with a cycle of two or three days (twenty-six client-days), chosen so that between them every fix type appears and clears, one client is healthy every day, and several have no fix but something a specialist would raise. The day is the date's ordinal modulo the cycle length. Four invented mail services supply the SPF includes. DKIM records hold real public keys generated once at 2,048, 1,024 and 512 bits; the private halves were never kept.
- **Why:** Phase 4 records model output for every one of these days and Phase 5 shows them, so they are fixed early and kept small. A cycle that repeats means a blocklisted client is listed again every third day; for a demo that is the point.
- **To undo:** edit or add files under `backend/fixtures/clients/` and `backend/fixtures/zones/`; `backend/tests/test_seeded.py` names which client-day shows which fix. Not a measure change: no eval case is a seeded client, and a test keeps their domains apart.
- **Status:** to review

## 2026-11-19, Phase 0: the model's input shape is fixed now, with these fields

- **Decided:** `backend/src/domain_health/models.py` defines what the model receives (`SnapshotInput`): the domain, the three checks, the seeded sources and the fix list, with the fields listed in `evals/RUBRIC.md` under "The input". Rates are percentages, volume is two seven-day counts, open rate is two thirty-day values with the earlier one null under 60 days of age. The other option was to leave the shape to Phase 1 and write the cases against a sketch.
- **Why:** an eval case is "exactly what the model receives", so the cases cannot be written without it. Phase 1 has to produce this shape.
- **To undo:** edit `models.py`, the rubric's "The input" section and the cases together. That touches the measure, so it is an owner-merged change.
- **Status:** to review

## 2026-11-19, Phase 0: twelve fix types and thirteen risk types

- **Decided:** the two closed lists in `backend/src/domain_health/types.py`, defined in `evals/RUBRIC.md`. The fix list was not in the spec; it had to exist because every case's input carries a fix list and the rubric has to draw the line between a fix and a risk. Thresholds for a fix: more than 10 SPF lookups, a DKIM key under 1,024 bits, complaints at 0.30% or more, bounces at 5.0% or more.
- **Why:** the plan asks for "about twelve" risk types and a written line between fix and risk. Each risk type sits on the judgment side of one of those lines.
- **To undo:** edit the lists, the rubric and the affected cases. Owner-merged, as above. The Phase 0 merge is the sign-off.
- **Status:** to review

## 2026-11-19, Phase 0: second-read objections taken into the rubric before sign-off

- **Decided:** after the second read, `spf_weak_all` is expected only for `?all` or no `all` while DMARC is not enforcing; `~all` is acceptable whatever DMARC says. The draft had `~all` without enforcing DMARC as expected. Cases 07, 12, 16, 19 and 20 were changed to match and to be realistic (no earlier open rate on a domain under 60 days; no `high` grade on an 18-day-old domain or on one with no SPF or DMARC). The other option was to leave the draft and only list the objections.
- **Why:** the second reader's reason is sound: receivers treat a soft fail much like a hard one, and with `p=none` the real gap is DMARC, already its own type. The objections not taken are listed in the phase log for the owner.
- **To undo:** restore the `spf_weak_all` lines in `evals/RUBRIC.md` and the five case files from the phase log's description. Owner-merged.
- **Status:** to review

## 2026-11-19, Phase 0: the Firestore emulator comes from a pinned `firebase-tools` in `emulator/`

- **Decided:** `emulator/package.json` pins `firebase-tools` 15.37.0 and `make check` runs the emulator-marked tests inside `firebase emulators:exec`, with the project ID `demo-domain-health`. The other options were the gcloud emulator component (it would install software and go near the machine's gcloud) or downloading the emulator jar by hand.
- **Why:** pinned by a lockfile, the same in CI and locally, and it touches no gcloud configuration. One smoke test (`backend/tests/test_emulator_smoke.py`) shows the wiring works now, so Phase 3 does not have to change CI.
- **To undo:** delete `emulator/`, the emulator line in the Makefile's `check-backend`, the JDK and emulator install steps in `.github/workflows/ci.yml` and the smoke test. CI is a guard file, so that is owner-merged.
- **Status:** to review

## 2026-11-19, Phase 0: the Makefile finds Node 24 and a JDK of 21 or later by itself

- **Decided:** where the default `node` is older than 24 and nvm has a 24, the Makefile puts that one first on the PATH for its own commands; on a Mac it asks `/usr/libexec/java_home -v 21+` for a JDK. Nothing on the machine is changed. The other option was to stop and ask the owner to switch defaults.
- **Why:** this machine's defaults are Node 20 and JDK 17; Node 24.22 and JDK 23 are installed. Installing or switching software is on the irreversible list; using what is there is not.
- **To undo:** delete the two blocks at the top of the `Makefile` and put Node 24 and a JDK of 21 or later first on the PATH yourself.
- **Status:** to review

## 2026-11-19, Phase 0: scaffold choices that differ from a plain reading of the docs

- **Decided:** (1) `pydantic-settings` is not installed yet; `docs/decisions/dependencies.md` now says Phase 4. (2) The test client uses `httpx2`, because the installed Starlette deprecates `httpx` for it. (3) The frontend keeps the generator's `cacheComponents` and `partialPrefetching` settings and its Tailwind loader for Turbopack, drops the web fonts and the generator's logo files, and uses system fonts until `docs/DESIGN.md` exists. (4) `frontend/src/content/claim.ts` exists now and the page shows the claim, so the claim pin has something to check in both toolchains. (5) `frontend/src/content/claim.test.ts` is added to `.claude/hooks/measure-paths.txt`: it pins the claim too.
- **Why:** (1) nothing reads settings yet and an unused dependency is noise; (2) and (3) follow the libraries as installed; (4) and (5) make the pin real from the first commit and guard it like the backend's.
- **To undo:** (1) `cd backend && uv add pydantic-settings`. (2) `uv remove --dev httpx2 && uv add --dev httpx`. (3) edit `frontend/next.config.ts` and `frontend/src/app/layout.tsx`. (4) and (5) delete the two files and the line in `measure-paths.txt` (owner-merged).
- **Status:** to review

## 2026-11-19, Phase 0: how "better than the baseline" is decided on the open cases (now reported, not a bar: decision 0012)

- **Decided:** in `docs/SPEC.md` and `backend/src/domain_health/evals/comparison.py`: over the three runs, on the open set, the model's harmful count is no higher than the baseline's, its precision is at least 0.80, it finds on average at least one more expected item per run, and in at least two runs the gain is real and comes from at least two cases. The last part is the owner's, from the answers to issue #3; the rest is the build's. The first draft also held precision to the baseline's; the sixth review showed the baseline's precision on the open set is 1.00 by construction, so that draft demanded a perfect score and one noise pick would have failed the claim. The other options were to keep that knowingly, or to add an open call on which the baseline loses precision. A second draft said only "higher coverage than the baseline's"; the seventh review showed that one extra item in one run of three would have met it, which is inside the noise, so the gain has to be one item per run.
- **Why:** the owner's answer said "if the model does no better than the baseline on the open cases", which needed a definition before any score exists, so that it cannot be chosen to fit one. This one uses only the measures already defined, cannot be met by trading harmful output for coverage, and still holds precision to the bar the owner set. The numbers this gives on the cases as they stand are in the pull request and are printed by the harness in Phase 2; they are not written into the spec, so they cannot drift.
- **To undo:** edit the paragraph "The model beside the baseline" in `docs/SPEC.md`, `backend/src/domain_health/evals/comparison.py` and its tests. Owner-merged.
- **Status:** to review

## 2026-11-19, Phase 0: public guidance documents are named in open-case notes

- **Decided:** the notes of the open cases, decision 0010 and (later) the README may name the public documents the owner asked the calls to rest on: the bulk-sender requirements published by Google and by Yahoo, and M3AAWG's best practices. To make the written rules agree with that, one sentence was added to rule 6 in `CLAUDE.md` and to the "Done when" line in `docs/SPEC.md`: "The tools and hosts the project runs on, and the public guidance documents its eval labels cite, are named as what they are." Nothing else in either rule changed, except that the spec line now says "client, company or person" where it said "company or person": both still say none of those anywhere in the tree or the history. A case's `input`, which is what the model receives, still holds no real name.
- **Why:** the owner's answer to issue #2 asks for exactly this grounding, by name.
- **To undo:** replace the names in the notes of `evals/cases/31` to `40` and in decision 0010 with "public bulk-sender requirements", and delete the added sentence from rule 6 in `CLAUDE.md` and from the "Done when" line in `docs/SPEC.md`. Owner-merged (the cases are the measure, and both files are the owner's).
- **Status:** to review

## 2026-11-19, Phase 0: who has seen the open cases, and who writes the prompt

- **Decided:** the ten open cases were written by a separate agent, fixed by a second one, and checked by this session through tests only: it never opened the case files. It meant not to read the agents' summary table and list of doubts either, but saw both while putting them into the pull request description. So the rule is moved to where it can hold: in Phase 2 the prompt is written and changed by an agent with fresh context that is given the rubric and the table cases only, and gets table-case results only. The reviewer and the challenger, which never write a prompt, read the open cases in full. The other option was to treat the open cases like the table cases.
- **Why:** the owner asked that the open cases come from an agent that never sees the prompt and stay out of prompt tuning. The session that builds Phase 0 may be the one that builds Phase 2.
- **To undo:** nothing to undo. To tighten it further, have a different person or a new session with no memory of this one run Phase 2, and keep it away from the Phase 0 pull request's description.
- **Status:** to review
