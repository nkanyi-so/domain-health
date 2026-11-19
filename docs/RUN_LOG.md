# Run log

Written by the build, one line per event, oldest first. Lines are only ever added, by `.claude/hooks/run-log.sh`, the merge gate and `stop.sh`; nobody edits or reorders one. It is committed with `docs/PLAN.md`, so a fresh clone carries on from it. `bin/run-report.sh` in the harness reads it, and `/harness-retro` starts from that report.

Tab-separated: UTC time, phase, event, detail, spend so far in USD. Events: `phase-started`, `review`, `verify`, `challenge`, `checkpoint`, `gate-refused`, `gate-merged`, `merged` (a merge the gate did not make or did not get to record), `stop-opened`, `stop-closed`.

```text
2026-11-19T14:05:13Z	0	phase-started	0: scaffold, process layer and the measure	0.00
2026-11-19T14:33:08Z	0	review	one blocking finding @ 0a7b46b	0.00
2026-11-19T14:37:15Z	0	review	one blocking finding @ 8f9390e	0.00
2026-11-19T14:40:42Z	0	review	one blocking finding @ ec5aa41	0.00
