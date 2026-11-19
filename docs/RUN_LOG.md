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
