#!/bin/bash
# Writes one event into docs/RUN_LOG.md, for the events the scripts cannot see. The merge gate and
# stop.sh write their own.
#
#   run-log.sh <event> "<detail>" [phase]   phase defaults to the number in the branch name
#   run-log.sh flush                        only moves lines that are waiting into the file
#
# Events: phase-started, review, verify, challenge, checkpoint, merged, stop-closed.
#   merged       a merge the gate did not make (the owner's) or did not get to record
#   stop-closed  a stop that had no issue to close
# Every call also moves the lines the gate and stop.sh left waiting into the file, in order. Then
# commit docs/RUN_LOG.md together with docs/PLAN.md: a line that is not committed and pushed does
# not survive a fresh clone.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HERE/harness-lib.sh"
usage() { echo "usage: run-log.sh <phase-started|review|verify|challenge|checkpoint|merged|stop-closed> \"<detail>\" [phase] | flush" >&2; exit 1; }
event="${1:-}"
case "$event" in
  flush) [ $# -eq 1 ] || usage ;;
  phase-started|review|verify|challenge|checkpoint|merged|stop-closed)
    [ $# -ge 2 ] && [ $# -le 3 ] && [ -n "$2" ] || usage
    case "${3:-}" in *[!0-9]*) echo "run-log: the phase must be a number" >&2; exit 1 ;; esac
    phase="-"; [ -z "${3:-}" ] || phase=$((10#$3))
    if [ "$phase" = "-" ] && [ "$(run_log_phase)" = "-" ]; then
      echo "run-log: this branch is not named phase-<number>, so give the phase: run-log.sh $event \"<detail>\" <phase>" >&2; exit 1
    fi
    run_log "$phase" "$event" "$2" ;;
  *) usage ;;
esac
counts=$(run_log_flush) || { echo "run-log: could not write $RUN_LOG_REL" >&2; exit 1; }
echo "run-log: ${counts% *} line(s) added to $RUN_LOG_REL. Commit it with docs/PLAN.md."
[ "${counts#* }" = "0" ] || echo "run-log: ${counts#* } waiting line(s) were not log lines the log's rule allows (most likely a write cut short) and were set aside in the git folder as harness-run-log.rejected, not put in the log." >&2
