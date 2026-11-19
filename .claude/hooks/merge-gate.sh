#!/bin/bash
# The run-through merge gate: the only way a run merges its own phase.
# Usage: bash .claude/hooks/merge-gate.sh <pull-request-number> [--dry-run]
#
# It merges only when every line below holds, and it reads what it can from GitHub and from the
# default branch, not from the branch under test:
#   - docs/STANDING.md on the default branch says "mode: run-through"
#   - the branch is phase-<N>, N is not 0 and N is not a checkpoint
#   - the pull request is open, not a draft, from this repository, onto the default branch
#   - the default branch is protected: status checks are required, at least one of them is a job
#     from this project's CI, and the rule holds for administrators too (a classic rule or a ruleset)
#   - the local checkout is clean and is the pull request's head commit
#   - the diff touches no guard file, nothing that states the claim or the measure
#   - no gate, checklist item or phase heading that is in the plan on the default branch was changed
#   - the phase log carries reviewer, verifier and challenger verdicts for the code as pushed
#   - nothing is waiting on the owner, and the spend the plan records is within the cap
#   - docs/RUN_LOG.md, if the diff has it, is the default branch's copy with whole log lines added
#   - every workflow run on that exact commit has finished, CI is green on it, and every required
#     check has reported on it
#
# Exit codes: 0 merged (or would merge, with --dry-run)   2 not merged, the owner is needed
#             3 not yet (CI still running)                 4 could not check   5 GitHub refused the merge
# Anything it cannot read counts as a refusal. On 2, 4 or 5: do not merge any other way. It is a stop.
# A merge, and every refusal with 2, 4 or 5, is written to the run log (docs/RUN_LOG.md) through
# harness-lib.sh, as a line that waits inside the git folder: the gate never changes a tracked file.
# A dry run writes nothing.
#
# What this is not: proof against an author that lies. The verdict lines and the spend figure are
# written into the log by the session that wrote the code, and the phase number comes from the
# branch name. The gate catches a stale or missing check, a touched guard, a changed gate and a
# red build. It does not see a Makefile or a test config that quietly checks less: that is the
# reviewer's to catch. The wall is still CI plus branch protection on the default branch, which is
# why the gate will not merge without it.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HERE/harness-lib.sh"

PR=""; DRY=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    ''|*[!0-9]*) echo "usage: merge-gate.sh <pull-request-number> [--dry-run]" >&2; exit 4 ;;
    *) PR="$a" ;;
  esac
done
[ -n "$PR" ] || { echo "usage: merge-gate.sh <pull-request-number> [--dry-run]" >&2; exit 4; }

# WHY names the check that is running, in a word, so the run log can count refusals by reason.
WHY="pull-request"
logged() { [ "$DRY" -eq 1 ] || run_log "${PHASE:--}" "$1" "$2"; }
refuse() { echo "merge-gate: NOT MERGED, the owner is needed: $1" >&2; logged gate-refused "exit=2 reason=$WHY pr=#$PR: $1"; exit 2; }
later()  { echo "merge-gate: not yet: $1" >&2; exit 3; }
broken() { echo "merge-gate: NOT MERGED, could not check: $1" >&2; logged gate-refused "exit=4 reason=$WHY pr=#$PR: $1"; exit 4; }
lower()  { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

REPO=$(harness_repo) || broken "cannot tell which GitHub repository this is (set HARNESS_REPO=owner/name)"
pr=$(api "repos/$REPO/pulls/$PR" 2>/dev/null) || broken "cannot read pull request #$PR in $REPO"
repo=$(api "repos/$REPO" 2>/dev/null) || broken "cannot read $REPO"
BASE=$(printf '%s' "$repo" | json 'd["default_branch"]') || broken "bad answer from GitHub"
state=$(printf '%s' "$pr" | json 'd["state"]') || broken "bad answer from GitHub"
draft=$(printf '%s' "$pr" | json 'd.get("draft", False)')
SHA=$(printf '%s' "$pr" | json 'd["head"]["sha"]')
ref=$(printf '%s' "$pr" | json 'd["head"]["ref"]')
base_ref=$(printf '%s' "$pr" | json 'd["base"]["ref"]')
head_repo=$(printf '%s' "$pr" | json '(d["head"].get("repo") or {}).get("full_name", "")')
[ -n "$BASE" ] && [ -n "$SHA" ] && [ -n "$ref" ] || broken "bad answer from GitHub"

[ "$state" = "open" ] || refuse "pull request #$PR is $state, not open"
[ "$draft" = "false" ] || refuse "pull request #$PR is a draft"
case "$BASE" in phase-*) refuse "the default branch is $BASE, a phase branch. The intake's first commit belongs on main, and Phase 0 is merged into it by the owner" ;; esac
[ "$base_ref" = "$BASE" ] || refuse "pull request #$PR targets $base_ref, not the default branch $BASE"
[ "$(lower "$head_repo")" = "$(lower "$REPO")" ] || refuse "pull request #$PR comes from another repository ($head_repo)"

# --- the standing answers, as the owner last merged them -------------------------------------
WHY="mode"
standing=$(api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/docs/STANDING.md?ref=$BASE" 2>/dev/null | tr -d '\r') \
  && [ -n "$standing" ] || refuse "no docs/STANDING.md on $BASE, so this project is gated"
standing_one() { # exactly one "key:" line, or the gate cannot say which the owner meant
  local n
  n=$(printf '%s\n' "$standing" | grep -c "^$1:")
  [ "$n" = "1" ] || refuse "docs/STANDING.md on $BASE has $n '$1:' lines; the gate needs exactly one"
  printf '%s\n' "$standing" | standing_value "$1"
}
mode=$(standing_one mode) || exit 2
[ "$mode" = "run-through" ] || refuse "docs/STANDING.md on $BASE says mode: ${mode:-<empty>}, not run-through"

WHY="phase"
case "$ref" in
  phase-[0-9]*) PHASE=$(printf '%s' "$ref" | sed -E 's/^phase-([0-9]+).*/\1/') ;;
  *) refuse "branch $ref is not named phase-<number>, so the gate cannot tell which phase this is" ;;
esac
case "$ref" in phase-"$PHASE"|phase-"$PHASE"-*) ;; *) refuse "branch $ref is not named phase-<number> or phase-<number>-<words>" ;; esac
PHASE=$((10#$PHASE))
[ "$PHASE" -ne 0 ] || refuse "Phase 0 is always merged by the owner"
WHY="checkpoint"
checkpoints=$(standing_one checkpoints) || exit 2
case "$checkpoints" in
  none) ;;
  '') refuse "the checkpoints line in docs/STANDING.md on $BASE is empty (write 'checkpoints: none' to switch them off)" ;;
  *[!0-9,\ ]*) refuse "cannot read the checkpoints line in docs/STANDING.md on $BASE: $checkpoints" ;;
  *) for c in $(printf '%s' "$checkpoints" | tr ',' ' '); do
       [ "$((10#$c))" -ne "$PHASE" ] || refuse "Phase $PHASE is a checkpoint: the owner reads the evidence and merges"
     done ;;
esac

# --- the wall: branch protection on the default branch ------------------------------------------
# The gate is not the wall. Without required checks that hold for administrators, any other route
# to the default branch skips everything above and below. So no protection, no merge.
WHY="protection"
required=$(protection_required "$REPO" "$BASE") \
  || refuse "the default branch $BASE is not protected the way a run-through needs: ${required:-could not be checked}. $(protection_howto "$BASE")"
[ -n "$required" ] || refuse "the default branch $BASE requires no status checks. $(protection_howto "$BASE")"

# --- the checkout is the commit GitHub has ----------------------------------------------------
WHY="checkout"
[ "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" = "$SHA" ] || refuse "the local checkout is not the pull request's head commit ($SHA). Push, or check out the branch"
# The run log may hold lines not committed yet: the gate reads nothing from it, and GitHub merges the commit, not this folder.
dirty=$(git -C "$ROOT" status --porcelain --untracked-files=no -- ':(top)' ':(top,exclude)docs/RUN_LOG.md' 2>/dev/null) || broken "cannot read the state of the working tree"
[ -z "$dirty" ] || refuse "the working tree has uncommitted changes to tracked files"

# --- what the diff touches ----------------------------------------------------------------------
WHY="guard-or-measure"
files=$(api --paginate "repos/$REPO/pulls/$PR/files?per_page=100" 2>/dev/null | python3 -c '
import json, sys
text, dec, i, out = sys.stdin.read(), json.JSONDecoder(), 0, []
while i < len(text):
    while i < len(text) and text[i].isspace(): i += 1
    if i >= len(text): break
    page, i = dec.raw_decode(text, i)
    for f in page:
        out.append(f["filename"])
        if f.get("previous_filename"): out.append(f["previous_filename"])
print("\n".join(out))') || broken "cannot list the files in pull request #$PR"
[ -n "$files" ] || broken "pull request #$PR lists no changed files"
[ "$(printf '%s\n' "$files" | wc -l)" -lt 2900 ] || refuse "the diff is too large for GitHub to list in full"

# The measure list must say something: at least one pattern, or the single word "none".
measure=$(api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/.claude/hooks/measure-paths.txt?ref=$BASE" 2>/dev/null | tr -d '\r') \
  || refuse "no .claude/hooks/measure-paths.txt on $BASE"
patterns=""
while IFS= read -r pattern || [ -n "$pattern" ]; do
  pattern="${pattern#"${pattern%%[![:space:]]*}"}"
  pattern="${pattern%"${pattern##*[![:space:]]}"}"
  case "$pattern" in ''|'#'*) continue ;; esac
  pattern=$(lower "$pattern")
  while :; do case "$pattern" in ./*) pattern="${pattern#./}" ;; /*) pattern="${pattern#/}" ;; */) pattern="${pattern%/}" ;; *) break ;; esac; done
  [ -n "$pattern" ] && patterns="$patterns$pattern
"
done <<<"$measure"
[ -n "$patterns" ] || refuse ".claude/hooks/measure-paths.txt on $BASE names nothing. List the files that state the claim or define the measure, or write the one word: none"
[ "$patterns" = "none
" ] && patterns=""
touched=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  lf=$(lower "$f")
  case "$lf" in
    .claude/*|*/.claude/*|.githooks/*|.github/*|claude.md|*/claude.md|docs/standing.md|docs/spec.md|docs/harness/*|docs/profiles/*|.harness-version|.gitleaks.toml|*/.gitleaks.toml|.gitleaksignore|*/.gitleaksignore)
      touched="$touched $f"; continue ;;
  esac
  while IFS= read -r pattern; do
    [ -n "$pattern" ] || continue
    # A pattern names a file, a glob, or a folder and everything under it.
    # shellcheck disable=SC2254
    case "$lf" in $pattern|*/$pattern|$pattern/*|*/$pattern/*) touched="$touched $f"; break ;; esac
  done <<<"$patterns"
done <<<"$files"
[ -z "$touched" ] || refuse "the diff touches a guard, or what states the claim or the measure:$touched"

# --- the plan: its gates are the measure too ----------------------------------------------------
WHY="plan-gates"
PLAN_TXT=$(git -C "$ROOT" show "$SHA:docs/PLAN.md" 2>/dev/null | tr -d '\r') && [ -n "$PLAN_TXT" ] || refuse "no docs/PLAN.md in the commit under test"
BASE_PLAN=$(api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/docs/PLAN.md?ref=$BASE" 2>/dev/null | tr -d '\r') \
  && [ -n "$BASE_PLAN" ] || refuse "no docs/PLAN.md on $BASE to compare the gates against"
changed=$(BASE_PLAN="$BASE_PLAN" HEAD_PLAN="$PLAN_TXT" python3 -c '
import os, re
def locked(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("**Gate:**") or re.match(r"^## Phase\b", s): out.append(s)
        m = re.match(r"^- \[[ xX]\] (.*)$", s)
        if m: out.append("- [ ] " + m.group(1).strip())
    return out
head = set(locked(os.environ["HEAD_PLAN"]))
gone = [l for l in locked(os.environ["BASE_PLAN"]) if l not in head]
print("\n".join(l[:90] for l in gone[:3]))') || broken "could not compare the plan with the one on $BASE"
[ -z "$changed" ] || refuse "a gate, a checklist item or a phase heading that is in docs/PLAN.md on $BASE was changed or removed (boxes may be ticked and lines added, nothing more): $changed"

# --- the run log: lines are added, nothing else ---------------------------------------------------
# No verdict covers this file and the reviewer does not read it, so the gate does: a plain file,
# holding what the default branch holds, plus whole log lines.
WHY="run-log"
scratch=$(mktemp -d 2>/dev/null) || broken "could not make a temporary folder"
trap 'rm -rf "$scratch"' EXIT
# Whether the default branch has a log is read from the folder's listing, so a failed read
# of the file is never taken for "there is none". The listing must be a real one (the plan the gate
# has just read from that folder is in it), and the copy fetched must be the one the listing names.
listed=$(api "repos/$REPO/contents/docs?ref=$BASE" 2>/dev/null | python3 -c '
import json, re, sys
d = json.load(sys.stdin)
if not isinstance(d, list) or not all(isinstance(f, dict) and isinstance(f.get("name"), str) for f in d): sys.exit(1)
if not any(f["name"] == "PLAN.md" for f in d): sys.exit(1)
logs = [f for f in d if f["name"] == "RUN_LOG.md"]
if not logs: print("none"); sys.exit(0)
sha = logs[0].get("sha")
if len(logs) != 1 or not isinstance(sha, str) or not re.match(r"^[0-9a-f]{40,64}$", sha): sys.exit(1)
print(sha)' 2>/dev/null) || broken "cannot list docs/ on $BASE, so cannot tell whether a run log is there"
if [ "$listed" != "none" ]; then
  api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/docs/RUN_LOG.md?ref=$BASE" > "$scratch/base" 2>/dev/null \
    || broken "cannot read docs/RUN_LOG.md on $BASE"
  [ "$(git -C "$ROOT" hash-object "$scratch/base" 2>/dev/null)" = "$listed" ] || broken "the copy of docs/RUN_LOG.md read from $BASE is not the one GitHub lists there (a cut-off or wrong answer)"
fi
entry=$(git -C "$ROOT" ls-tree "$SHA" -- docs/RUN_LOG.md 2>/dev/null) || broken "cannot read the commit under test"
if [ -n "$entry" ]; then
  case "$entry" in "100644 blob "*) ;; *) refuse "docs/RUN_LOG.md is not a plain file in the commit under test (a link, a folder, or marked as a program)" ;; esac
  git -C "$ROOT" show "$SHA:docs/RUN_LOG.md" > "$scratch/head" 2>/dev/null || broken "cannot read docs/RUN_LOG.md in the commit under test"
  run_log_added "$scratch/base" "$scratch/head" \
    || refuse "docs/RUN_LOG.md is not the copy on $BASE with log lines added: a line was changed or removed, or something that is not a log line was put in it (or $BASE has gained log lines this branch does not have: then update the branch from $BASE)"
elif [ -f "$scratch/base" ]; then
  refuse "docs/RUN_LOG.md is on $BASE and not in the commit under test: the run log was removed"
fi

# --- the independent checks, for the code as pushed -------------------------------------------
WHY="verdict"
covers() { # covers <commit>   true when nothing but the phase log, the notes and the run log changed between it and HEAD
  local c="$1" changed f
  git -C "$ROOT" merge-base --is-ancestor "$c" HEAD 2>/dev/null || return 1
  changed=$(git -C "$ROOT" diff --no-renames --name-only "$c" HEAD 2>/dev/null) || return 1
  while IFS= read -r f; do
    case "$f" in ''|docs/PLAN.md|docs/HARNESS_NOTES.md|docs/RUN_LOG.md) ;; *) return 1 ;; esac
  done <<<"$changed"
  return 0
}
verdict() { # verdict <who> <passing words>...   the last "<who>-verdict:" line in the plan must pass
  local who="$1" line said commit full want found=0 re
  shift
  line=$(grep -E "^${who}-verdict:" <<<"$PLAN_TXT" | tail -1)
  [ -n "$line" ] || refuse "the phase log has no ${who}-verdict line"
  re="^${who}-verdict: (.*) @ ([0-9a-f]{7,40})\$"
  [[ "$line" =~ $re ]] || refuse "cannot read \"$line\" (write: ${who}-verdict: $1 @ <commit>, and nothing after the commit)"
  said="${BASH_REMATCH[1]}"; commit="${BASH_REMATCH[2]}"
  for want in "$@"; do [ "$said" = "$want" ] && found=1; done
  [ "$found" -eq 1 ] || refuse "${who}-verdict is \"$said\", not \"$1\""
  full=$(git -C "$ROOT" rev-parse --verify -q "$commit^{commit}" 2>/dev/null)
  case "$full" in "$commit"*) ;; *) refuse "${who}-verdict names $commit, which is not a commit here" ;; esac
  covers "$full" || refuse "${who}-verdict is for $commit, and code has changed since. Run the $who again on the code as pushed"
}
verdict reviewer "no blocking findings"
verdict verifier "pass" "not needed"
verdict challenger "no change" "not needed"

# --- nothing waiting, spend within the cap ------------------------------------------------------
WHY="waiting"
waiting=$(printf '%s\n' "$PLAN_TXT" | waiting_state) || broken "could not read the 'Waiting on you' section"
case "$waiting" in
  clear) ;;
  heading) refuse "docs/PLAN.md must have exactly one 'Waiting on you' section" ;;
  *) refuse "docs/PLAN.md has something under 'Waiting on you' (when nothing is open, the section holds the one line: Nothing.)" ;;
esac
open_stops=$(api "repos/$REPO/issues?labels=waiting-on-owner&state=open&per_page=5" 2>/dev/null | json 'len(d)') \
  || broken "cannot list open waiting-on-owner issues"
[ "$open_stops" = "0" ] || refuse "there is an open waiting-on-owner issue (if it was closed seconds ago, GitHub's list can lag: run the gate again)"
WHY="spend"
cap=$(standing_one spend-cap-usd) || exit 2
[[ "$cap" =~ ^[0-9]+(\.[0-9]+)?$ ]] || refuse "cannot read the spend cap in docs/STANDING.md on $BASE (\"$cap\"): it must be a plain number, such as 20 or 12.50"
[ "$(grep -c '^Spend: ' <<<"$PLAN_TXT")" = "1" ] || refuse "docs/PLAN.md must have exactly one 'Spend: \$X of ...' line"
spent=$(sed -nE 's/^Spend: \$([0-9]+(\.[0-9]+)?) of .*/\1/p' <<<"$PLAN_TXT")
[ -n "$spent" ] || refuse "cannot read the 'Spend: \$X of ...' line in docs/PLAN.md"
python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) <= float(sys.argv[2]) else 1)' "$spent" "$cap" 2>/dev/null \
  || refuse "the plan records spend of \$$spent, past the cap of \$$cap"

# --- CI on that exact commit ----------------------------------------------------------------------
WHY="ci"
# Every workflow started for this commit must have finished first. A job that has not begun (one
# behind `needs:`) has no check run yet, so the check runs alone can look green too early.
flows=$(api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=100" 2>/dev/null) || broken "cannot read the workflow runs for $SHA"
unfinished=$(printf '%s' "$flows" | python3 -c '
import json, sys
d = json.load(sys.stdin)
runs = d["workflow_runs"]
if d.get("total_count", len(runs)) > len(runs): print("toomany"); sys.exit()
going = sorted({str(r.get("name") or "?") for r in runs if r.get("status") != "completed"})
# A workflow that failed to start, or was cancelled before a job began, leaves no check run to be red.
failed = sorted({str(r.get("name") or "?") for r in runs if r.get("status") == "completed" and r.get("conclusion") not in ("success", "neutral", "skipped")})
print("going " + ", ".join(going) if going else "failed " + ", ".join(failed) if failed else "")') || broken "bad workflow answer from GitHub"
case "$unfinished" in
  '') ;;
  toomany) refuse "more workflow runs on $SHA than the gate reads in one page" ;;
  going\ *) later "a workflow has not finished on $SHA: ${unfinished#going }" ;;
  *) refuse "a workflow did not succeed on $SHA: ${unfinished#failed }" ;;
esac
runs=$(api "repos/$REPO/commits/$SHA/check-runs?per_page=100" 2>/dev/null) || broken "cannot read CI results for $SHA"
ci=$(printf '%s' "$runs" | python3 -c '
import json, sys
d = json.load(sys.stdin)
runs = d.get("check_runs", [])
if not runs: print("none"); sys.exit()
if d.get("total_count", len(runs)) > len(runs): print("toomany"); sys.exit()
if any(r.get("status") != "completed" for r in runs): print("running"); sys.exit()
bad = [r.get("name", "?") for r in runs if r.get("conclusion") not in ("success", "neutral", "skipped")]
print("failed " + ", ".join(bad) if bad else "green")') || broken "bad CI answer from GitHub"
case "$ci" in
  green) ;;
  running) later "CI is still running on $SHA" ;;
  none) later "no CI run has reported on $SHA yet (if CI never starts, that is a stop)" ;;
  toomany) refuse "more CI jobs reported on $SHA than the gate reads in one page" ;;
  *) refuse "CI $ci on $SHA" ;;
esac
status=$(api "repos/$REPO/commits/$SHA/status" 2>/dev/null) || broken "cannot read commit statuses for $SHA"
st=$(printf '%s' "$status" | json '"none" if not d.get("total_count") else d.get("state", "")') || broken "bad status answer from GitHub"
case "$st" in
  none|success) ;;
  pending) later "a commit status is still pending on $SHA" ;;
  *) refuse "a commit status is $st on $SHA" ;;
esac

# Every required check must have reported on this commit: one that nothing reports is waited for,
# not read as green. And one of them must be a job of this
# project's CI: a required check that nothing here runs protects nothing.
WHY="protection"
# A job of this project's CI is a check run made by GitHub Actions from the workflows in the
# repository. Another app's check (a host's deploy check) is a required check, but not the CI.
jobs=$(printf '%s' "$runs" | json '[r.get("name", "") for r in d.get("check_runs", []) if (r.get("app") or {}).get("slug") == "github-actions"]') || broken "bad CI answer from GitHub"
passed=$( { printf '%s' "$runs" | json '[r.get("name", "") for r in d.get("check_runs", [])]' \
         && printf '%s' "$status" | json '[s.get("context", "") for s in d.get("statuses", []) if s.get("state") == "success"]'; } ) || broken "bad status answer from GitHub"
from_ci=0; unreported=""
while IFS= read -r c; do
  [ -n "$c" ] || continue
  if grep -Fxq -- "$c" <<<"$jobs"; then from_ci=1
  elif grep -Fxq -- "$c" <<<"$passed"; then :
  else unreported="$unreported \"$c\""; fi
done <<<"$required"
loose=$(grep -Fxv -f <(printf '%s\n' "$required") <<<"$jobs" | grep . | sort -u | tr '\n' ',' | sed 's/,$//; s/,/, /g')
[ -z "$unreported" ] || later "a required check has not reported on $SHA:$unreported (if it never does, the name in the protection rule matches no job: that is a stop)"
[ "$from_ci" -eq 1 ] || refuse "none of the required checks on $BASE ($(printf '%s' "$required" | tr '\n' ',' | sed 's/,$//; s/,/, /g')) is a job that ran in this project's CI on $SHA. $(protection_howto "$BASE")"

# Said, not refused: the wall holds only the jobs it names.
[ -z "$loose" ] || echo "merge-gate: note: these CI jobs ran but are not required checks on $BASE, so only this gate holds them: $loose. Owner: add them to the required checks."

if [ "$DRY" -eq 1 ]; then echo "merge-gate: every check holds. Would merge #$PR ($ref, $SHA) into $BASE."; exit 0; fi

# sha= makes GitHub refuse if the branch moved after the checks above.
if out=$(api -X PUT "repos/$REPO/pulls/$PR/merge" -f "sha=$SHA" -f "merge_method=${HARNESS_MERGE_METHOD:-merge}" 2>&1); then
  echo "merge-gate: merged #$PR ($ref, $SHA) into $BASE."
  logged gate-merged "pr=#$PR $ref $SHA into $BASE"
  exit 0
fi
echo "merge-gate: GITHUB REFUSED THE MERGE of #$PR. Every gate check passed; the refusal is GitHub's:" >&2
printf '%s\n' "$out" | head -5 >&2
echo "merge-gate: do not try another way to merge. This is a stop: the pull request is open and ready, and the owner merges it." >&2
logged gate-refused "exit=5 reason=github pr=#$PR: GitHub refused the merge: $(printf '%s' "$out" | first_line)"
exit 5
