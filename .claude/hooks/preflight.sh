#!/bin/bash
# Run before a run-through, on any machine: says whether this environment can carry the run,
# and lists what only the owner can supply. Reads names, never values.
# Usage: bash .claude/hooks/preflight.sh      Exit 0 ready, 1 something is missing.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
. "$HERE/harness-lib.sh"
missing=0
good() { echo "ok:      $1"; }
warn() { echo "warning: $1"; }
need() { echo "MISSING: $1"; missing=$((missing+1)); }

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then where="a cloud session"; else where="this machine"; fi
echo "preflight on $where, in $ROOT"

for t in git make python3 gh; do
  if command -v "$t" >/dev/null 2>&1; then good "$t is installed"; else need "$t is not installed"; fi
done
if command -v gitleaks >/dev/null 2>&1; then good "gitleaks is installed"
else warn "gitleaks is not installed: commits here are not scanned for secrets before they are made (CI still scans)"; fi
if [ "$(git -C "$ROOT" config core.hooksPath 2>/dev/null)" = ".githooks" ]; then good "the pre-commit hook is on"
else need "the pre-commit hook is off. Run: git config core.hooksPath .githooks (a fresh clone needs it every time; make setup does it)"; fi

S="$ROOT/docs/STANDING.md"
if [ ! -f "$S" ]; then
  need "docs/STANDING.md does not exist: the intake writes it"
else
  mode=$(standing_value mode < "$S")
  case "$mode" in
    run-through|gated) good "mode: $mode" ;;
    *) need "docs/STANDING.md has no usable mode line (gated or run-through)" ;;
  esac
  for key in mode owner spend-cap-usd checkpoints; do
    [ "$(grep -c "^$key:" "$S")" = "1" ] || need "docs/STANDING.md must have exactly one '$key:' line (the merge gate refuses otherwise)"
  done
  v=$(standing_value owner < "$S")
  case "$v" in ''|*'{{'*) need "docs/STANDING.md: owner is not filled in" ;; *) good "owner: $v" ;; esac
  # The same reading the merge gate does, so "ready" here means the gate can read them too.
  v=$(standing_value spend-cap-usd < "$S")
  if [[ "$v" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then good "spend-cap-usd: $v"
  else need "docs/STANDING.md: spend-cap-usd must be a plain number such as 20 or 12.50 (it is \"$v\")"; fi
  v=$(standing_value checkpoints < "$S")
  case "$v" in
    none) good "checkpoints: none" ;;
    ''|*[!0-9,\ ]*) need "docs/STANDING.md: checkpoints must be phase numbers such as 2, 5, or the word none (it is \"$v\")" ;;
    *) good "checkpoints: $v" ;;
  esac
  # Names of the environment variables the build needs. Only whether each is there is reported.
  for name in $(standing_value requires-env < "$S" | tr ',' ' '); do
    case "$name" in none|*'{{'*) continue ;; esac
    case "$name" in *[!A-Za-z0-9_]*) need "requires-env: \"$name\" is not a variable name"; continue ;; esac
    if [ -n "${!name:-}" ]; then good "$name is set"
    elif [ -f "$ROOT/.env" ] && grep -qE "^(export[[:space:]]+)?$name=." "$ROOT/.env" 2>/dev/null; then good "$name is in .env"
    elif [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then need "$name is not set. Owner: add it to this cloud environment's variables"
    else need "$name is not set. Owner: put it in .env or the shell, as the project's README says"; fi
  done
fi
M="$ROOT/.claude/hooks/measure-paths.txt"
if [ -f "$M" ] && grep -qvE '^[[:space:]]*(#.*)?$' "$M"; then good "measure-paths.txt names something"
else need ".claude/hooks/measure-paths.txt names nothing. List the files that state the claim or define the measure, or write the one word: none"; fi

if REPO=$(harness_repo); then
  if repo=$(api "repos/$REPO" 2>/dev/null); then
    good "GitHub answers for $REPO over REST"
    [ "$(printf '%s' "$repo" | json '(d.get("permissions") or {}).get("push", False)')" = "true" ] \
      && good "this login can push to $REPO" || need "this login cannot push to $REPO"
    base=$(printf '%s' "$repo" | json 'd["default_branch"]')
    case "$base" in phase-*) need "the default branch is $base, a phase branch. The first commit belongs on main" ;; esac
    method="${HARNESS_MERGE_METHOD:-merge}"
    case "$method" in
      merge) allowed=$(printf '%s' "$repo" | json 'd.get("allow_merge_commit", True)') ;;
      squash) allowed=$(printf '%s' "$repo" | json 'd.get("allow_squash_merge", True)') ;;
      rebase) allowed=$(printf '%s' "$repo" | json 'd.get("allow_rebase_merge", True)') ;;
      *) allowed="false" ;;
    esac
    [ "$allowed" = "true" ] && good "the repository allows the '$method' merge method" \
      || need "this repository does not allow the '$method' merge method the gate uses. Allow it, or set HARNESS_MERGE_METHOD to merge, squash or rebase"
    # The same reading the merge gate does. In run-through mode the gate refuses without it, so it is a stop here too.
    if required=$(protection_required "$REPO" "$base"); then
      good "$base is protected: status checks are required, administrators included ($(printf '%s' "$required" | tr '\n' ',' | sed 's/,$//; s/,/, /g')). The merge gate also wants one of them to be a job of this project's CI"
    elif [ "${mode:-}" = "run-through" ]; then
      need "$base is not protected the way a run-through needs: ${required:-could not be checked}. The merge gate will merge nothing. $(protection_howto "$base")"
    else
      warn "branch protection on $base: ${required:-could not be checked}. Without it, CI is advice. A run-through will not merge until it is on"
    fi
    if [ -f "$S" ] && remote=$(api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/docs/STANDING.md?ref=$base" 2>/dev/null); then
      rmode=$(printf '%s\n' "$remote" | standing_value mode)
      [ "$rmode" = "${mode:-}" ] && good "mode on $base matches this checkout" \
        || warn "mode on $base is ${rmode:-<missing>}; the merge gate goes by $base, not by this checkout"
    else
      warn "docs/STANDING.md is not on $base yet, so the merge gate treats the project as gated"
    fi
  else
    need "GitHub does not answer for $REPO with this login (gh api repos/$REPO failed)"
  fi
else
  need "cannot tell which GitHub repository this is. Set HARNESS_REPO=owner/name"
fi

# This project's own checks: the owner actions in docs/STANDING.md that a script can confirm.
# The script prints its own ok and MISSING lines; its exit status is how many are missing.
if [ -f "$ROOT/scripts/preflight-project.sh" ]; then
  bash "$ROOT/scripts/preflight-project.sh"
  missing=$((missing+$?))
else
  need "scripts/preflight-project.sh does not exist: Phase 0 writes it"
fi

if [ "$missing" -eq 0 ]; then echo "preflight: ready"; exit 0; fi
echo "preflight: $missing thing(s) missing. Each MISSING line is a stop for the owner, asked once, together."
exit 1
