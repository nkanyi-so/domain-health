#!/bin/bash
# Shared helpers for merge-gate.sh, stop.sh and preflight.sh. Sourced, not run.
# Every GitHub call goes through `gh api` (REST). `gh pr` and `gh issue` use GraphQL, which a
# Claude Code cloud session's GitHub proxy rejects, so they are not used anywhere in the layer.
# Needs bash, git, python3 and gh.

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# owner/name of the GitHub repository. HARNESS_REPO overrides, for a clone whose origin is
# not a GitHub address (a proxy, a bundle).
harness_repo() {
  if [ -n "${HARNESS_REPO:-}" ]; then printf '%s\n' "$HARNESS_REPO"; return 0; fi
  local url
  url=$(git -C "$ROOT" remote get-url origin 2>/dev/null) || return 1
  printf '%s' "$url" | python3 -c '
import re, sys
m = re.search(r"[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", sys.stdin.read().strip())
if not m: sys.exit(1)
print(m.group(1) + "/" + m.group(2))'
}

api() { gh api "$@"; }

# standing_value <key>   reads "key: value" from STANDING text on stdin. Empty when absent.
standing_value() {
  sed -n "s/^$1:[[:space:]]*//p" | head -1 | sed 's/[[:space:]]*$//'
}

# json <python expression over d>   reads JSON on stdin, prints the value. Fails on bad JSON.
json() {
  python3 -c '
import json, sys
d = json.load(sys.stdin)
v = eval(sys.argv[1])
if isinstance(v, bool): v = "true" if v else "false"
if v is None: v = ""
if isinstance(v, (list, tuple)): print("\n".join(str(x) for x in v))
else: print(v)' "$1"
}

# The "Waiting on you" section runs from its heading to the line "<!-- end: waiting on you -->"
# (or, if that marker is gone, to the next "## Phase" or "## Status" heading). A "---" rule or a
# "##" heading inside a question does not end it.
_waiting_py='
import re, sys
text = sys.stdin.read().replace("\r", "")
want = sys.argv[1]
heads = re.findall(r"(?m)^## Waiting on you[ \t]*$", text)
if len(heads) != 1:
    print("heading" if want == "state" else "", end="\n" if want == "state" else "")
    sys.exit(0 if want == "state" else 1)
body = re.split(r"(?m)^## Waiting on you[ \t]*$", text, maxsplit=1)[1]
m = re.search(r"(?m)^<!-- end: waiting on you -->[ \t]*$", body)
if m: body = body[:m.start()]
else:
    m = re.search(r"(?m)^## (Phase|Status)\b", body)
    if m: body = body[:m.start()]
if want == "state":
    bare = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    lines = [l.strip() for l in bare.splitlines() if l.strip() and l.strip() != "---"]
    print("clear" if lines == ["Nothing."] else "open")
else:
    print(body.strip("\n"))
'
# waiting_state   reads a plan on stdin; prints clear, open, or heading (none, or more than one).
waiting_state() { python3 -c "$_waiting_py" state; }
# waiting_block <PLAN.md>   prints the whole block, however it is laid out.
waiting_block() { python3 -c "$_waiting_py" block < "$1"; }

# first_line   first non-blank line of stdin, trimmed.
first_line() {
  tr -d '\r' | awk 'NF{sub(/^[[:space:]]+/,""); sub(/[[:space:]]+$/,""); print; exit}'
}

# --- branch protection ----------------------------------------------------------------------------
# protection_required <owner/name> <branch>
# Exit 0 and one required status check per line when the branch is protected the way a run-through
# needs: status checks are required, and the rule holds for administrators too. Either kind counts:
# a classic branch protection rule, or a ruleset. Exit 1 and one line saying what is wrong
# otherwise. What cannot be read counts as not there.
_protection_py='
import json, os, re, sys
mode, d = sys.argv[1], sys.argv[2]
def load(name):
    try:
        with open(os.path.join(d, name)) as f: return json.load(f)
    except Exception: return None
def said(name):
    try:
        with open(os.path.join(d, name)) as f: lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    except Exception: return ""
    return lines[0][:200] if lines else ""
def contexts(items, key="context"):
    out = set()
    for c in items or []:
        if isinstance(c, dict): c = c.get(key)
        if isinstance(c, str) and c.strip(): out.add(c.strip())
    return out
classic, rules = load("classic"), load("rules")
status_rules = [r for r in rules if isinstance(r, dict) and r.get("type") == "required_status_checks"] if isinstance(rules, list) else []
if mode == "ids":
    ids = {r.get("ruleset_id") for r in status_rules}
    print("\n".join(str(i) for i in sorted(i for i in ids if isinstance(i, int) and not isinstance(i, bool))))
    sys.exit(0)
need, why = set(), []
if isinstance(classic, dict):
    rsc = classic.get("required_status_checks") or {}
    ctx = contexts(rsc.get("contexts")) | contexts(rsc.get("checks"))
    admins = (classic.get("enforce_admins") or {}).get("enabled") is True
    if not ctx: why.append("the branch protection rule requires no status checks")
    elif not admins: why.append("the branch protection rule does not apply to administrators")
    else: need |= ctx
for r in status_rules:
    rid = r.get("ruleset_id")
    label = "ruleset %s" % rid
    ctx = contexts((r.get("parameters") or {}).get("required_status_checks"))
    rs = load("ruleset-%s" % rid) if isinstance(rid, int) and not isinstance(rid, bool) else None
    if not ctx: why.append(label + " requires no status checks")
    elif not isinstance(rs, dict): why.append(label + " could not be read, so the gate cannot tell who may bypass it")
    elif rs.get("enforcement") != "active": why.append(label + " is not active")
    elif rs.get("bypass_actors") != [] or rs.get("current_user_can_bypass") != "never":
        why.append(label + " can be bypassed (its bypass list is not empty or was not shown to this login, or this login may bypass it)")
    else: need |= ctx
if need:
    print("\n".join(sorted(need)))
    sys.exit(0)
if not why:
    if not isinstance(classic, dict) and not isinstance(rules, list):
        told = said("classic.err") or said("rules.err")
        why.append("neither the branch protection rule nor the rulesets could be read" + (" (GitHub said: %s)" % told if told else ""))
    else:
        why.append("no rule on the branch requires status checks")
print("; ".join(why))
sys.exit(1)
'
protection_required() {
  local repo="$1" base="$2" dir id rc
  dir=$(mktemp -d 2>/dev/null) || { echo "could not make a temporary folder to read the protection into"; return 1; }
  api "repos/$repo/branches/$base/protection" > "$dir/classic" 2> "$dir/classic.err" || rm -f "$dir/classic"
  api "repos/$repo/rules/branches/$base?per_page=100" > "$dir/rules" 2> "$dir/rules.err" || rm -f "$dir/rules"
  # A rule from a ruleset says what it requires, not who may walk past it: that is on the ruleset.
  while IFS= read -r id; do
    case "$id" in ''|*[!0-9]*) continue ;; esac
    api "repos/$repo/rulesets/$id" > "$dir/ruleset-$id" 2>/dev/null || rm -f "$dir/ruleset-$id"
  done < <(python3 -c "$_protection_py" ids "$dir" 2>/dev/null)
  python3 -c "$_protection_py" check "$dir"; rc=$?
  rm -rf "$dir"
  [ "$rc" -eq 0 ]
}
# protection_howto <branch>   what the owner switches on, in one line.
protection_howto() {
  printf '%s' "Owner: in the repository's Settings, under Branches or Rules, protect $1: switch on 'Require status checks to pass', pick this project's CI jobs as the required checks (the template's are named check and secrets), and switch on 'Do not allow bypassing the above settings' (in a ruleset: leave the bypass list empty). A private repository on GitHub's free plan cannot be protected: make it public or upgrade the account to GitHub Pro."
}

# --- the run log ----------------------------------------------------------------------------------
# docs/RUN_LOG.md is the run's own record: one tab-separated line per event, oldest first, only
# ever appended to. run_log writes a line; run_log_flush moves waiting lines into the file.
#
# A script must be able to log without touching a tracked file (the merge gate wants a clean tree,
# and a refusal has to be loggable without causing the next one). So a new line waits in a file
# inside the git folder, where git never sees it, and reaches docs/RUN_LOG.md when run-log.sh is
# next called. The loop calls that before each commit of the plan and commits the two together.
# Waiting lines do not survive a fresh clone; committed ones do.
RUN_LOG_REL="docs/RUN_LOG.md"
_run_log_header() {
  printf '%s\n' '# Run log' '' \
    'Written by the build, one line per event, oldest first. Lines are only ever added, by `.claude/hooks/run-log.sh`, the merge gate and `stop.sh`; nobody edits or reorders one. It is committed with `docs/PLAN.md`, so a fresh clone carries on from it. `bin/run-report.sh` in the harness reads it, and `/harness-retro` starts from that report.' '' \
    'Tab-separated: UTC time, phase, event, detail, spend so far in USD. Events: `phase-started`, `review`, `verify`, `challenge`, `checkpoint`, `gate-refused`, `gate-merged`, `merged` (a merge the gate did not make or did not get to record), `stop-opened`, `stop-closed`.' '' \
    '```text'
}
_run_log_spool() {
  local g
  g=$(git -C "$ROOT" rev-parse --absolute-git-dir 2>/dev/null) && [ -d "$g" ] || return 1
  printf '%s/harness-run-log.pending\n' "$g"
}
# run_log_phase   the phase number in the branch name, or "-".
run_log_phase() {
  local b
  b=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
  case "$b" in
    phase-[0-9]*) b=$(printf '%s' "$b" | sed -E 's/^phase-([0-9]+).*/\1/'); printf '%s\n' "$((10#$b))" ;;
    *) echo "-" ;;
  esac
}
_run_log_spend() {
  local s
  s=$(sed -nE 's/^Spend: \$([0-9]+(\.[0-9]+)?) of .*/\1/p' "$ROOT/docs/PLAN.md" 2>/dev/null | head -1)
  printf '%s\n' "${s:-?}"
}
_run_log_file() { # makes sure the file is there, under its header, and ends in a line break
  local f="$ROOT/$RUN_LOG_REL"
  if [ ! -s "$f" ]; then mkdir -p "$(dirname "$f")" && _run_log_header > "$f" || return 1; fi
  [ -z "$(tail -c1 "$f")" ] || echo >> "$f"
}
# run_log_added <file as it was, or a path that does not exist> <file as it is>
# True when the second is the first with whole log lines added and nothing else. A log that is new
# must be the header above, then log lines. The merge gate uses it: the reviewer does not read this
# file, so nothing but log lines may ride in it.
# One rule for what a log line is, used by the flush and by the gate: five fields, a UTC time, a
# short phase and event, a spend that is a number or "?", no control bytes, at most 1000 bytes.
_run_log_py='
import os, re, sys
LINE = re.compile(rb"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\t[A-Za-z0-9._-]{1,20}\t[a-z0-9_-]{1,30}\t[^\x00-\x1f\x7f]*\t(\?|\d{1,9}(\.\d{1,9})?)$")
def good(l): return len(l) <= 1000 and LINE.match(l) is not None
def read(p):
    with open(p, "rb") as f: return f.read()
if sys.argv[1] == "added":
    old = read(sys.argv[2]) if os.path.isfile(sys.argv[2]) else None
    if old is not None and not old.strip(): old = None      # an empty file there is no log yet
    new, start = read(sys.argv[3]), (old if old is not None else read(sys.argv[4]))
    if not new.startswith(start): sys.exit(1)
    if start and not start.endswith(b"\n") and new != start and not new[len(start):].startswith(b"\n"): sys.exit(1)
    sys.exit(0 if all(good(l) for l in new[len(start):].split(b"\n") if l) else 1)
# sift <waiting lines> <the log> <rejects>: whole lines go to the log, anything else is set aside.
# A line already in the log (a flush that died after writing, then ran again) is not added twice.
have = set(read(sys.argv[3]).split(b"\n")) if os.path.isfile(sys.argv[3]) else set()
keep, drop = [], []
for l in read(sys.argv[2]).split(b"\n"):
    if not l or l in have: continue
    have.add(l)
    (keep if good(l) else drop).append(l)
if keep:
    with open(sys.argv[3], "ab") as f: f.write(b"\n".join(keep) + b"\n")
if drop:
    with open(sys.argv[4], "ab") as f: f.write(b"\n".join(drop) + b"\n")
print("%d %d" % (len(keep), len(drop)))
'
run_log_added() {
  local header rc
  header=$(mktemp 2>/dev/null) || return 1
  _run_log_header > "$header"
  python3 -c "$_run_log_py" added "$1" "$2" "$header"
  rc=$?; rm -f "$header"; return $rc
}
# run_log <phase, or - for the branch's> <event> <detail>   never fails its caller.
run_log() {
  local phase="${1:--}" event="${2:-}" detail="${3:-}" line spool spend
  [ -n "$event" ] || return 0
  case "$phase" in -|'') phase=$(run_log_phase) ;; esac
  # Shaped here to exactly what the log's line rule accepts, so an honest line is never set aside:
  # no control bytes, the detail cut by bytes, a spend the rule can read.
  phase=$(printf '%s' "$phase" | tr -c 'A-Za-z0-9.-' '_' | LC_ALL=C cut -c1-20)
  event=$(printf '%s' "$event" | tr -c 'a-z0-9-' '_' | LC_ALL=C cut -c1-30)
  detail=$(printf '%s' "$detail" | LC_ALL=C tr '\t\r\n' '   ' | LC_ALL=C tr -d '\000-\037\177' | LC_ALL=C cut -c1-400)
  spend=$(_run_log_spend)
  [[ "$spend" =~ ^[0-9]{1,9}(\.[0-9]{1,9})?$ ]] || spend="?"
  line=$(printf '%s\t%s\t%s\t%s\t%s' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$phase" "$event" "$detail" "$spend")
  if spool=$(_run_log_spool); then
    # A line cut short (a killed write) must not swallow this one.
    { if [ -s "$spool" ] && [ -n "$(tail -c1 "$spool")" ]; then echo >> "$spool"; fi
      printf '%s\n' "$line" >> "$spool"; } 2>/dev/null || true
  else
    { _run_log_file && printf '%s\n' "$line" >> "$ROOT/$RUN_LOG_REL"; } 2>/dev/null || true
  fi
  return 0
}
# run_log_flush   moves the waiting lines into docs/RUN_LOG.md. Prints how many it moved, and how
# many it set aside: a line that is not whole (a write cut short) would make the gate refuse the
# log, so it goes to harness-run-log.rejected in the git folder instead of into the file.
run_log_flush() {
  local spool f pid counts
  spool=$(_run_log_spool) || { echo "0 0"; return 0; }
  # Lines an earlier flush took aside and never finished with (it was killed) wait again.
  for f in "$spool".[0-9]*; do
    [ -f "$f" ] || continue
    pid="${f##*.}"
    case "$pid" in *[!0-9]*) continue ;; esac
    kill -0 "$pid" 2>/dev/null && continue
    cat "$f" >> "$spool" 2>/dev/null && rm -f "$f"
  done
  [ -s "$spool" ] || { echo "0 0"; return 0; }
  _run_log_file || return 1
  # Take the waiting lines aside first, so two calls at once cannot both move the same line.
  mv "$spool" "$spool.$$" 2>/dev/null || { echo "0 0"; return 0; }
  if counts=$(python3 -c "$_run_log_py" sift "$spool.$$" "$ROOT/$RUN_LOG_REL" "${spool%.pending}.rejected"); then rm -f "$spool.$$"
  else cat "$spool.$$" >> "$spool"; rm -f "$spool.$$"; return 1; fi
  echo "$counts"
}
