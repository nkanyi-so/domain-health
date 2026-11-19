# Principles

These hold on every project. Anything specific to a stack or a kind of product belongs in the project or in a profile (`profiles/`), not here.

## 1. Docs are the source of truth

In this order: `docs/SPEC.md` (what), `docs/ARCHITECTURE.md` (how), `docs/PLAN.md` (phases, gates, progress log), `docs/decisions/` (why). If code and docs disagree, stop and say so. Do not quietly pick one.

## 2. One gate command

Every project exposes `make check`. It runs format check, lint, type check, tests, and any other check that costs nothing to run. It must exit 0 before a commit. The pre-commit hook and CI run the same command, so "passes locally" and "passes in CI" mean the same thing. A measured bar (an eval score against its threshold) is not in it: that is judged at the phase gate, on evidence, so a result that misses its bar can still be committed and read.

The harness knows no language. Whatever the stack, the project wraps its own tools behind `make check` and `make format FILE=<path>`. The layer needs bash, make and python3, so it runs on macOS, Linux and WSL, not on native Windows.

## 3. Evidence, not claims

A gate is ticked only when the commands run and their real output are pasted into the phase log. "Should work" is not evidence. Never weaken a test, a check or a type check to make a gate pass. Say what is failing instead.

The phase log in `docs/PLAN.md` is the one record: the plan summary, what the reviewer and verifier reported in their own words, what was fixed, and the gate evidence. The pull request links to it instead of repeating it.

## 4. The author does not grade the work

The session that wrote the code does not approve it. Review, verification and the challenge to the claim are done by agents with a fresh context (see section 7), and CI runs the gate on a machine the author does not control.

Who merges is a standing answer, per project (`docs/STANDING.md`):

- **Gated.** I approve the plan at the start, read the evidence at the gate, and merge. This is the default for adopted code.
- **Run-through.** The run merges its own phase, but only through the merge gate script, which merges when the independent checks have passed on the code as pushed, CI is green on that commit, nothing is waiting on me, and the diff touches neither the guards nor what states the claim or the measure, the plan's gates included. The merge is mechanical; the judgement that the work is good is still not the author's. Phase 0 and the checkpoints are mine in both modes.

The run-through rests on evidence from one build (article-agent, ten phase merges): no merge review of mine found a fault the reviewer, the verifier or CI had missed, and nine of ten merges changed nothing. What I did add came from reading evidence at two points, the first working draft and the first eval results. Those are the default checkpoints, and the three questions I asked there are now the `challenger` agent's.

## 5. Safe by default

- Secrets live in the environment. `.env` is ignored, blocked from reads and edits, and refused by the pre-commit hook. A secret scan runs before every commit where gitleaks is installed (the hook says so loudly where it is not) and over the full history in CI.
- Tests and CI never call a live or paid service. Use a fake.
- Anything that spends money or writes to an outside system asks first, every time. In run-through mode the asking is done once, up front: a paid step the plan lists runs while its worst case stays under the spend cap, and an outward step runs only if `docs/STANDING.md` lists it as allowed. Past either line it is a stop.
- Anything public that spends money has a rate limit and a daily budget cap.
- No real client names, terms, schemas or numbers in any public repo.
- No new direct runtime dependency without one line of reason in `docs/decisions/dependencies.md`.
- The guards guard themselves: a change to settings, hooks, agents, the working loop, the pre-commit hook or CI asks the human first. In run-through mode the question moves from the edit to the merge: the change is live in that session at once, but the gate will not merge a phase that contains it, so I see it at the pull request before it reaches the default branch.
- Deny rules on shell commands are a courtesy, not a wall; a differently spelled command walks past them. The real guards are branch protection on `main` and CI. In run-through mode the merge gate checks that the wall is there (required status checks that hold for administrators) and merges nothing without it.

## 6. Library APIs change

Before planning a phase, check current docs or the installed source for every library it uses. If the library contradicts the docs in the repo, follow the library and note it in the phase log.

## 7. How sub-agents are used

A sub-agent is a separate agent with its own fresh context. Use one for three reasons only:

- **Independence.** Someone who did not write the work should check it. `reviewer` (phase diff against the docs, plus a security mode before release), `verifier` (runs the app like a user) and `challenger` (is the claim true as an absolute, is the measure too noisy, could code check what a judge or a person caught).
- **Isolation.** Reading a lot of code would flood the main session. `auditor` maps and grades an existing codebase and returns only its conclusions.
- **Parallelism.** Only when tasks touch different files and need nothing from each other. Give each its own git worktree.

Do not split one feature across agents, and do not use a sub-agent to plan. The main session owns the plan and `docs/PLAN.md`. Each sub-agent reports findings; it does not tick gates.

## 8. When the plan stops fitting

If a gate cannot pass, or the spec turns out to be wrong, stop. Say what is failing and why. The docs change first: a decision record, then the spec or plan, approved by me. Then the phase is re-planned. Working around a gate, or building something the docs do not describe, is never the fix.

A run-through stops for these and nothing else: a credential or another step only I can do; spend that could pass the cap; anything irreversible or outward-facing that I have not allowed in advance; a gate that cannot pass after a real attempt; a change to what the project claims or how it is measured; a checkpoint; a phase the merge gate leaves for me. A smaller call is made and written in `docs/DECISIONS_TO_REVIEW.md` with its reason and how to undo it.

A stop asks everything at once, in plain language, with a recommendation, and it has to reach me: the block under "Waiting on you" in `docs/PLAN.md`, the same block in a GitHub issue assigned to me, and a notification where the machine can send one. Progress is readable from the Status block at the top of `docs/PLAN.md` without opening a log. Every stop, merge, refusal and check is also one line in `docs/RUN_LOG.md`, so the retro counts them instead of remembering them.

## 9. Every mistake improves the system

When the agent gets something wrong, fix the cause where it will be read next time: the project's `CLAUDE.md` if it is specific to that project, this repo if it would apply anywhere. Log it in `docs/HARNESS_NOTES.md` as it happens. Keep `CLAUDE.md` short: rules the agent would otherwise break, not documentation.

The harness is held to its own rules: `make check` here runs `bin/selftest.sh`, and CI runs it on every pull request.
