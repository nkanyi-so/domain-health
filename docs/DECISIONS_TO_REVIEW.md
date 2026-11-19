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

## 2026-11-19, Phase 0: the model's input shape is fixed now, with these fields

- **Decided:** `backend/src/domain_health/models.py` defines what the model receives (`SnapshotInput`): the domain, the three checks, the seeded sources and the fix list, with the fields listed in `evals/RUBRIC.md` under "The input". Rates are percentages, volume is two seven-day counts, open rate is two thirty-day values with the earlier one null under 60 days of age. The other option was to leave the shape to Phase 1 and write the cases against a sketch.
- **Why:** an eval case is "exactly what the model receives", so twenty cases cannot be written without it. Phase 1 has to produce this shape.
- **To undo:** edit `models.py`, the rubric's "The input" section and the twenty cases together. That touches the measure, so it is an owner-merged change.
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
