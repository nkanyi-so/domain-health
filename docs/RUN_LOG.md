# Run log

Written by the build, one line per event, oldest first. Lines are only ever added, by `.claude/hooks/run-log.sh`, the merge gate and `stop.sh`; nobody edits or reorders one. It is committed with `docs/PLAN.md`, so a fresh clone carries on from it. `bin/run-report.sh` in the harness reads it, and `/harness-retro` starts from that report.

Tab-separated: UTC time, phase, event, detail, spend so far in USD. Events: `phase-started`, `review`, `verify`, `challenge`, `checkpoint`, `gate-refused`, `gate-merged`, `merged` (a merge the gate did not make or did not get to record), `stop-opened`, `stop-closed`.

```text
