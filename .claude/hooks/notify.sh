#!/bin/bash
# Tells the owner, on a Mac, that this project is waiting on them: a notification naming the
# project and what it needs, and the same sound twice so it is not mistaken for anything else.
# Two callers: the Notification hook in .claude/settings.json (hook JSON on stdin), and stop.sh
# (the need as the first argument).
# Anywhere it cannot run (a cloud session, Linux, no osascript) it does nothing and exits 0.
# It never fails and waits at most two seconds for its input: a notifier must not be able to
# stop the work.
# HARNESS_NOTIFY=off silences it. HARNESS_NOTIFY=print shows what it would send, for the self-test.
# HARNESS_NOTIFY_SOUND picks another sound from /System/Library/Sounds (default Submarine).
MODE="${HARNESS_NOTIFY:-on}"
[ "$MODE" = "off" ] && exit 0

NEED="${1:-}"
if [ -z "$NEED" ] && [ ! -t 0 ]; then
  # Read the hook input, but never wait for it: two seconds, then go on without.
  RAW=""
  IFS= read -r -t 2 -d '' RAW 2>/dev/null || true
  NEED=$(printf '%s' "$RAW" | python3 -c '
import json, sys
try: print((json.load(sys.stdin).get("message") or "")[:200])
except Exception: pass' 2>/dev/null)
fi
[ -n "$NEED" ] || NEED="The session is waiting for you."
NEED=$(printf '%s' "$NEED" | tr '\n\r' '  ' | cut -c1-200)
PROJECT=$(basename "${CLAUDE_PROJECT_DIR:-$PWD}")
TITLE="NEEDS YOU: $PROJECT"
SOUND="/System/Library/Sounds/${HARNESS_NOTIFY_SOUND:-Submarine}.aiff"

if [ "$MODE" = "print" ]; then printf '%s | %s\n' "$TITLE" "$NEED"; exit 0; fi
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && exit 0
[ "$(uname -s 2>/dev/null)" = "Darwin" ] || exit 0
command -v osascript >/dev/null 2>&1 || exit 0

# The text is passed as arguments, never pasted into the script, so it cannot run as code.
osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title (item 1 of argv)' -e 'end run' \
  "$TITLE" "$NEED" >/dev/null 2>&1 || true
if command -v afplay >/dev/null 2>&1 && [ -f "$SOUND" ]; then
  ( afplay "$SOUND"; afplay "$SOUND" ) >/dev/null 2>&1 </dev/null &
fi
exit 0
