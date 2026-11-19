# Run log

Written by the build, one line per event, oldest first. Lines are only ever added, by `.claude/hooks/run-log.sh`, the merge gate and `stop.sh`; nobody edits or reorders one. It is committed with `docs/PLAN.md`, so a fresh clone carries on from it. `bin/run-report.sh` in the harness reads it, and `/harness-retro` starts from that report.

Tab-separated: UTC time, phase, event, detail, spend so far in USD. Events: `phase-started`, `review`, `verify`, `challenge`, `checkpoint`, `gate-refused`, `gate-merged`, `merged` (a merge the gate did not make or did not get to record), `stop-opened`, `stop-closed`.

```text
2026-11-19T14:05:13Z	0	phase-started	0: scaffold, process layer and the measure	0.00
2026-11-19T14:33:08Z	0	review	one blocking finding @ 0a7b46b	0.00
2026-11-19T14:37:15Z	0	review	one blocking finding @ 8f9390e	0.00
2026-11-19T14:40:42Z	0	review	one blocking finding @ ec5aa41	0.00
2026-11-19T14:43:48Z	0	review	no blocking findings @ 2e989a7	0.00
2026-11-19T14:49:01Z	0	verify	pass @ 2e989a7	0.00
2026-11-19T14:49:01Z	0	challenge	change needed @ 2e989a7	0.00
2026-11-19T14:51:06Z	0	stop-opened	issue=#2 questions=0 asked: Phase 0: challenger says change needed; read the measure, answer, merge #1	0.00
2026-11-19T15:02:58Z	0	stop-closed	issue=#2 opened=2026-11-19T14:51:06Z note: Answered by the owner in the session: A1 with agent-drafted open cases, yes to B C D F, forty cases, all code checks, measure as drafted, owner actions done.	0.00
2026-11-19T15:19:07Z	0	review	blocking findings (5) @ b2e056c	0.00
2026-11-19T15:33:06Z	0	review	2 blocking findings @ 4c82fd0	0.00
2026-11-19T15:38:36Z	0	review	one blocking finding @ c7874ae	0.00
2026-11-19T15:43:42Z	0	review	no blocking findings @ 71d51ff	0.00
2026-11-19T15:46:55Z	0	verify	pass @ 71d51ff	0.00
2026-11-19T15:46:55Z	0	challenge	change needed @ 71d51ff	0.00
2026-11-19T15:47:34Z	0	stop-opened	issue=#3 questions=0 asked: Phase 0: challenger says the open cases need a change; choose A, B or C	0.00
2026-11-19T16:02:53Z	0	stop-closed	issue=#3 opened=2026-11-19T15:47:34Z note: Answered by the owner in the session: A, with a limit of one round and option C's wording as the fallback; redraft 34 and 38; reword the CLAIM.md line.	0.00
2026-11-19T16:24:03Z	0	review	blocking findings @ fb8ea98	0.00
2026-11-19T16:24:04Z	0	challenge	change needed @ fb8ea98	0.00
2026-11-19T16:33:31Z	0	review	blocking findings @ 618619f	0.00
2026-11-19T16:34:33Z	0	challenge	change needed @ 618619f	0.00
2026-11-19T16:39:49Z	0	review	blocking findings @ 4870da3	0.00
2026-11-19T16:39:49Z	0	challenge	change needed @ 4870da3	0.00
2026-11-19T16:42:39Z	0	review	no blocking findings @ 4ae1da8	0.00
2026-11-19T16:42:39Z	0	challenge	no change @ 4ae1da8	0.00
2026-11-19T16:45:18Z	0	verify	pass @ 4ae1da8	0.00
2026-11-19T16:46:21Z	0	stop-opened	issue=#4 questions=3 asked: Phase 0 is ready: read the measure and merge #1	0.00
2026-11-19T17:05:37Z	1	stop-closed	issue=#4 opened=2026-11-19T16:46:20Z note: Answered by the owner's merge of pull request #1 at 2026-11-19T17:02:18Z.	0.00
2026-11-19T17:05:38Z	0	merged	pr=#1 merged by nkanyi-so at 2026-11-19T17:02:18Z	0.00
2026-11-19T17:09:43Z	1	phase-started	checks and rules	0.00
2026-11-19T17:28:32Z	1	review	blocking findings @ 6d64db6	0.00
2026-11-19T17:34:42Z	1	review	blocking findings @ 6473c88	0.00
2026-11-19T17:40:07Z	1	review	blocking findings @ 041e969	0.00
2026-11-19T17:45:35Z	1	review	no blocking findings @ 2e75ed2	0.00
2026-11-19T17:49:31Z	1	review	blocking findings @ 93ad50a	0.00
2026-11-19T17:55:29Z	1	review	blocking findings @ 36b32f0	0.00
2026-11-19T18:00:08Z	1	review	blocking findings @ 2e2e611	0.00
2026-11-19T18:05:01Z	1	review	blocking findings @ 12473e5	0.00
2026-11-19T18:13:53Z	1	review	blocking findings @ 65194d3	0.00
2026-11-19T18:18:55Z	1	review	blocking findings @ ffa6118	0.00
2026-11-19T18:24:18Z	1	review	blocking findings @ 285e74d	0.00
2026-11-19T18:28:22Z	1	review	no blocking findings @ 10f4114	0.00
2026-11-19T18:31:10Z	1	verify	pass @ 10f4114	0.00
2026-11-19T18:34:09Z	1	gate-merged	pr=#5 phase-1-checks-and-rules-clean ed6c4706734111a9fc6b0ffd5960ce014009a5bb into main	0.00
2026-11-19T18:36:25Z	2	phase-started	the model and the evals	0.00
