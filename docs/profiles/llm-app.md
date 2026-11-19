# Profile: LLM application

Add these on top of the base harness when the product calls a language model at run time.

## Rules where they suffice, the model only for judgment

Anything that can be computed, validated or enforced in code is. The model routes, words and judges. It does not do arithmetic, and its output is validated before use. Treat model output as untrusted input.

## Fixture client

The model sits behind one interface with two implementations: live and fixture. Tests, CI, `make check` and `make eval` use the fixture client only. A live run is a separate command that is never in the allow list, so it always asks. In run-through mode it runs without asking only while the worst case stays under the spend cap in `docs/STANDING.md`; the ledger below is what holds that, not the mode.

## Evals

- `docs/SPEC.md` ("How we know it works") holds the eval plan: what is checked exactly, what needs a judge, what must be refused, and the numbers that count as passing.
- `make check` runs the eval code's own tests and one fixture-mode run of the eval plumbing, end to end: cases load, the scorer runs, a results file can be written. That is free and gives the same answer every time. It does not fail on a threshold: a score below its bar is a result, not a broken build.
- `make eval` runs the evals, writes a results file into the repository (one known path, named in `CLAUDE.md`), and prints one line per measure: the score, its bar, and `met` or `missed`. It exits 0 whenever it ran, whatever the scores; with `STRICT=1` it exits non-zero when a bar is missed. By default it costs nothing: it scores with the fixture client or from outputs already recorded.
- CI runs `make eval STRICT=1` in a job of its own, named `eval`, beside `check`. The pre-commit hook runs `make check` only. So a missed bar never stops a commit, and the honest failure reaches the pull request for the owner to read, but the `eval` job is red there and the merge gate, which waits for every workflow on the commit to finish and wants every workflow and every job green, will not merge it. This is what keeps the move out of `make check` from loosening anything: a score that falls below its bar in a later phase is still caught by a machine, not only by whoever remembers to look. Phase 0 adds the job; the owner merges Phase 0.
- Every phase runs `make eval` before its review, whether or not the phase is about the evals, and its output goes in the phase log.
- The paid, live eval run is its own command (for example `make eval-live`). Neither `make check` nor `make eval` ever calls it, it is never in the allow list, and it writes the same results file and prints the same lines.
- Whether a bar is met is decided at the phase gate, not by `make check`. The output of the eval run the gate names is pasted into the phase log as evidence before the review, and the `challenger` reads it against the bars. A missed bar means the gate is not ticked, and that is a stop (principle 8). It is not a red commit: the results file and the log are committed, so the owner can read an honest failure.
- Never loosen an eval or its threshold to make a gate pass. If what an eval measures has to change, the old measure is still reported beside the new one, and the change is said wherever the score is.
- Say how many runs a threshold is measured over before measuring a fix against it. One run of a small case is noise.
- A worked example in a prompt never comes from the data the prompt is tested on. A test enforces it.
- Hand-labelled answers for a judge get a second read against the rule they test; a label the judge proves wrong is corrected, with the reason recorded.
- The demo's seeded data exercises every state the screen has.

## The three questions

Whenever a phase produces eval results, or touches the claim, an eval, a threshold, a judge or a label, the `challenger` agent, which did not write the work, reads the eval output against its bars and answers these in writing in the phase log:

1. Is the claim true as an absolute, or only for what the code and the judge can see?
2. Is the measurement too noisy to trust at one run per case?
3. Could anything the judge or a human caught be checked in code instead?

They are here because on the first full build each was asked by the owner while reading evidence at a merge, and by nobody else: the claim was false as an absolute and was reworded, one run per case moved by 0.2 with no cause and became three, and a wrong-speaker fault the judge kept finding became a rule in code. If any answer means the claim or the measure should change, the build stops for the owner, in either mode. The change is theirs to make.

The eval cases, thresholds, judge prompts, hand labels and the test that pins the claim's wording are listed in `.claude/hooks/measure-paths.txt`. A phase that touches one is merged by the owner. The results file is evidence, not the measure: it is not listed, and the reviewer checks that the numbers in it are the ones the code produces.

## Spend

Log cost and latency per call. A paid step runs behind a ledger with a hard stop, checked before every call at the most that call could cost. Anything public has a rate limit and a daily budget cap, and the reviewer checks both.
