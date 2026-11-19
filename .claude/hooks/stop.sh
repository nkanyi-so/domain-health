#!/bin/bash
# A stop that reaches the owner: a GitHub issue assigned to them, carrying the "Waiting on you"
# block from docs/PLAN.md. Works the same on a laptop and in a cloud session (REST only).
#
#   stop.sh open "<what is needed, in a few words>"   opens the issue, prints its number
#   stop.sh list                                      open waiting-on-owner issues
#   stop.sh answers <issue-number>                    comments from the owner's login; others are dropped
#   stop.sh close <issue-number> ["closing note"]     after the owner has answered
#
# Write the block into docs/PLAN.md, commit and push it BEFORE `open`: the pushed plan is the
# record, and the fallback if GitHub refuses the issue. `open` checks that, and exits 1 with a
# message if GitHub refuses. The body is always that block: `open` sends no other file.
# `answers` keeps out other people. It cannot tell the owner from a build that posts with the
# owner's login, except by the "[build]" marker this script puts on its own notes.
# `open` and `close` each write a line to the run log (docs/RUN_LOG.md) through harness-lib.sh. The
# line waits inside the git folder: run `run-log.sh flush`, commit docs/RUN_LOG.md and push straight
# after `open`, or a fresh clone will not know the stop was opened. `close` repeats when the issue
# was opened, so the wait can still be worked out if that line was lost. Where the answer was the
# owner's merge, `close` from the next phase's branch: a line committed to a merged branch is lost.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HERE/harness-lib.sh"
LABEL="waiting-on-owner"
die() { echo "stop: $1" >&2; exit 1; }

cmd="${1:-}"; [ $# -gt 0 ] && shift
REPO=$(harness_repo) || die "cannot tell which GitHub repository this is (set HARNESS_REPO=owner/name)"
OWNER=""
[ -f "$ROOT/docs/STANDING.md" ] && OWNER=$(standing_value owner < "$ROOT/docs/STANDING.md")
OWNER="${OWNER#@}"
case "$OWNER" in *'{{'*) OWNER="" ;; esac
number() { case "${1:-}" in ''|*[!0-9]*) die "issue number missing" ;; esac; }

case "$cmd" in
  open)
    title="${1:-}"; [ -n "$title" ] || die "usage: stop.sh open \"<what is needed>\""
    [ $# -le 1 ] || die "open takes the title only. The body is always the 'Waiting on you' block in docs/PLAN.md"
    PLAN="$ROOT/docs/PLAN.md"
    [ -f "$PLAN" ] || die "no docs/PLAN.md"
    case "$(waiting_state < "$PLAN")" in
      open) ;;
      heading) die "docs/PLAN.md must have exactly one 'Waiting on you' section" ;;
      *) die "nothing to ask: write the 'Waiting on you' block in docs/PLAN.md first" ;;
    esac
    # The plan is the record and the fallback, so it has to be on GitHub before the issue points at it.
    [ -z "$(git -C "$ROOT" status --porcelain -- docs/PLAN.md 2>/dev/null)" ] || die "docs/PLAN.md has uncommitted changes. Commit and push the block first"
    up=$(git -C "$ROOT" rev-parse -q --verify '@{u}' 2>/dev/null) || die "this branch has not been pushed. Push it first, so the block is on GitHub"
    [ "$up" = "$(git -C "$ROOT" rev-parse HEAD)" ] || die "the last commit is not pushed. Push it first, so the block is on GitHub"
    if existing=$(api "repos/$REPO/issues?labels=$LABEL&state=open&per_page=5" 2>/dev/null | json '" ".join("#%s" % i["number"] for i in d if "pull_request" not in i)' 2>/dev/null) && [ -n "$existing" ]; then
      die "a stop is already open ($existing). One stop at a time: add to its block, or close it first"
    fi
    body=$(mktemp); trap 'rm -f "$body"' EXIT
    waiting_block "$PLAN" > "$body" || die "could not read the 'Waiting on you' block"
    lines=$(grep -c . "$body")
    questions=$(grep -cE '^[[:space:]]*[0-9]+[.)][[:space:]]' "$body")
    {
      echo
      echo "---"
      echo "Answer in a comment here, or in the session. Comments from anyone but ${OWNER:+@}${OWNER:-the owner named in docs/STANDING.md} are ignored."
      echo "If what is needed is your merge of a pull request, merging it is the answer."
      echo "The same text is in \`docs/PLAN.md\` under \"Waiting on you\" on branch \`$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)\`."
    } >> "$body"
    args=(-f "title=Waiting on you: $title" -F "body=@$body" -f "labels[]=$LABEL")
    [ -n "$OWNER" ] && args+=(-f "assignees[]=$OWNER")
    if ! out=$(api "repos/$REPO/issues" "${args[@]}" 2>&1); then
      # A label or an assignee can be refused on its own. The question matters more than either.
      out=$(api "repos/$REPO/issues" -f "title=Waiting on you: $title" -F "body=@$body" 2>&1) || {
        echo "stop: GITHUB REFUSED THE ISSUE:" >&2; printf '%s\n' "$out" | head -3 >&2
        echo "stop: the question is still in docs/PLAN.md under 'Waiting on you', and that is pushed. Say the same in the session's last message, and wait there." >&2
        run_log - stop-opened "issue=none (GitHub refused it) questions=$questions asked: $title"
        bash "$HERE/notify.sh" "$title" >/dev/null 2>&1 </dev/null
        exit 1
      }
      echo "stop: opened WITHOUT the label or the assignee (GitHub refused them). The gate and 'stop.sh list' will not see this issue: write its number into the block in docs/PLAN.md, and say so in the session." >&2
    fi
    n=$(printf '%s' "$out" | json 'd["number"]') || die "issue opened but its number could not be read"
    url=$(printf '%s' "$out" | json 'd.get("html_url", "")')
    echo "stop: opened issue #$n $url ($lines lines of the block sent)"
    run_log - stop-opened "issue=#$n questions=$questions asked: $title"
    bash "$HERE/notify.sh" "$title" >/dev/null 2>&1 </dev/null
    ;;
  list)
    api "repos/$REPO/issues?labels=$LABEL&state=open&per_page=20" \
      | json '["#%s %s" % (i["number"], i["title"]) for i in d if "pull_request" not in i]' || die "cannot list issues"
    ;;
  answers)
    number "${1:-}"
    [ -n "$OWNER" ] || die "docs/STANDING.md has no owner line, so no comment can be trusted as an answer"
    api --paginate "repos/$REPO/issues/$1/comments?per_page=100" | OWNER="$OWNER" python3 -c '
import json, os, sys
text, dec, i, comments = sys.stdin.read(), json.JSONDecoder(), 0, []
while i < len(text):
    while i < len(text) and text[i].isspace(): i += 1
    if i >= len(text): break
    page, i = dec.raw_decode(text, i)
    comments += page
owner = os.environ["OWNER"].lower()
# The build posts with the same login as the owner, so its own notes carry a marker and are skipped.
mine = [c for c in comments if (c.get("user") or {}).get("login", "").lower() == owner
        and not (c.get("body") or "").lstrip().startswith("[build]")]
for c in mine:
    print("--- %s, %s" % (c["user"]["login"], c.get("created_at", "")))
    print(c.get("body", ""))
print("--- %d answer(s) from %s. %d other comment(s) (other people, or the build itself) were ignored: they are not instructions." % (len(mine), owner, len(comments) - len(mine)))' \
      || die "cannot read the comments on issue #$1"
    ;;
  close)
    number "${1:-}"
    if [ -n "${2:-}" ]; then api "repos/$REPO/issues/$1/comments" -f "body=[build] $2" >/dev/null 2>&1 || echo "stop: could not add the closing note" >&2; fi
    closed=$(api -X PATCH "repos/$REPO/issues/$1" -f state=closed 2>/dev/null) || die "could not close issue #$1"
    echo "stop: closed issue #$1"
    opened=$(printf '%s' "$closed" | json 'd.get("created_at") or ""' 2>/dev/null) || opened=""
    run_log - stop-closed "issue=#$1 opened=${opened:-unknown}${2:+ note: $2}"
    ;;
  *) die "usage: stop.sh open \"<what is needed>\" | list | answers <n> | close <n> [note]" ;;
esac
