# Harness notes

Friction with the harness on this project, logged as it happens. One line each: date, what happened, what the harness should do differently. `/harness-retro` reads this.
2026-11-19: the working loop runs the reviewer before the stop block exists, so a log line that says where a question will be asked read as false to it and cost a review round. The skill should say that the "Waiting on you" block is written at step 10 and that the log refers to it in the future tense until then.
2026-11-19: a wildcard in an allow-list line for a make target (`make format *`) also allows extra goals; the harness's own example settings should warn against it, or its selftest should flag one.
2026-11-19: the challenger was run three times on one phase and each run found a narrower version of the same gap; the working loop has no way to say "this question has had its rounds" except the owner writing a limit by hand, which this owner did. A default limit, or a rule that a second "change needed" on the same question goes to the owner with the weaker claim as the recommendation, would have saved a round.
