#!/bin/bash
# PreToolUse hook for Edit|Write: blocks secrets, lockfiles, git internals and generated files,
# and asks the human before the harness's own guard files are changed (gated mode).
# Exit 2 blocks the edit and sends the stderr message back to Claude as feedback.
# Project-specific generated files go in .claude/hooks/protected-paths.txt, one glob per line.
# Needs python3. If the input cannot be read, the edit is blocked rather than waved through.
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
if [ -z "$FILE_PATH" ]; then
  echo "Blocked: protect-files.sh could not read file_path from the hook input (is python3 installed?). Blocking to be safe." >&2
  exit 2
fi

case "$FILE_PATH" in
  .env.example|*/.env.example|.env.*.example|*/.env.*.example)
    ;;
  .env|*/.env|.env.*|*/.env.*)
    echo "Blocked: $FILE_PATH holds secrets. Never touch .env; document new variables in .env.example." >&2
    exit 2
    ;;
  .git|*/.git|.git/*|*/.git/*)
    echo "Blocked: $FILE_PATH is git internals. Use git commands instead." >&2
    exit 2
    ;;
  *.lock|*.lockb|*-lock.json|*-lock.yaml|go.sum|*/go.sum|Package.resolved|*/Package.resolved|gradle.lockfile|*/gradle.lockfile)
    echo "Blocked: $FILE_PATH is a lockfile. Change dependencies through the package manager." >&2
    exit 2
    ;;
esac

LIST="$CLAUDE_PROJECT_DIR/.claude/hooks/protected-paths.txt"
if [ -f "$LIST" ]; then
  while IFS= read -r pattern || [ -n "$pattern" ]; do
    # Trim surrounding whitespace (and a Windows line ending), or the glob silently never matches.
    pattern="${pattern#"${pattern%%[![:space:]]*}"}"
    pattern="${pattern%"${pattern##*[![:space:]]}"}"
    case "$pattern" in ''|'#'*) continue ;; esac
    # shellcheck disable=SC2254
    case "$FILE_PATH" in
      $pattern|*/$pattern)
        echo "Blocked: $FILE_PATH is generated or protected in this project. Change its source and regenerate." >&2
        exit 2
        ;;
    esac
  done < "$LIST"
fi

# The checks below go by where the path really points, so a different spelling of the same file
# (other case on a case-insensitive disk, ./ or //, a symlink) is the same file to them.
CANON=$(FILE_PATH="$FILE_PATH" ROOT="${CLAUDE_PROJECT_DIR:-$PWD}" python3 -c '
import os
root = os.path.realpath(os.environ["ROOT"])
f = os.environ["FILE_PATH"]
f = os.path.realpath(f if os.path.isabs(f) else os.path.join(root, f))
print((os.path.relpath(f, root) if f.startswith(root + os.sep) else f).lower())' 2>/dev/null)
[ -n "$CANON" ] || CANON=$(printf '%s' "$FILE_PATH" | tr '[:upper:]' '[:lower:]')

# The standing answers are the owner's. The intake writes the file once; from the moment it has a
# real mode line the agent does not edit it, in either mode. The owner changes it by hand.
case "$CANON" in
  docs/standing.md|*/docs/standing.md)
    case "$FILE_PATH" in /*) ABS="$FILE_PATH" ;; *) ABS="${CLAUDE_PROJECT_DIR:-$PWD}/$FILE_PATH" ;; esac
    if [ -f "$ABS" ] && grep -qE '^mode:[[:space:]]*(gated|run-through)[[:space:]]*$' "$ABS" 2>/dev/null; then
      echo "Blocked: $FILE_PATH holds the owner's standing answers and its mode is set. Put the change you want under 'Waiting on you' in docs/PLAN.md; the owner edits this file by hand." >&2
      exit 2
    fi
    ;;
esac

# The guard files themselves: not blocked (Phase 0 has to adapt them).
# Gated mode: the human is asked each time.
# Run-through mode: no question is asked, because nobody is there to answer it. That is not an
# approval. The edit takes effect in this session at once, and the merge gate refuses to merge any
# phase whose diff touches these files, so the owner sees it at the pull request. The one file a
# pull request never carries, settings.local.json, stays blocked.
case "$CANON" in
  .claude/settings.json|*/.claude/settings.json|.claude/settings.local.json|*/.claude/settings.local.json|.claude/hooks/*|*/.claude/hooks/*|.claude/agents/*|*/.claude/agents/*|.claude/skills/*|*/.claude/skills/*|.githooks/*|*/.githooks/*|.github/workflows/*|*/.github/workflows/*)
    STANDING="${CLAUDE_PROJECT_DIR:-$PWD}/docs/STANDING.md"
    MODE=""
    if [ "$(grep -c '^mode:' "$STANDING" 2>/dev/null)" = "1" ]; then
      MODE=$(sed -n 's/^mode:[[:space:]]*//p' "$STANDING" 2>/dev/null | sed 's/[[:space:]]*$//')
    fi
    if [ "$MODE" = "run-through" ]; then
      case "$CANON" in
        .claude/settings.local.json|*/.claude/settings.local.json)
          echo "Blocked: $FILE_PATH is never part of a pull request, so in run-through mode nobody would see this change. Put it under 'Waiting on you' in docs/PLAN.md." >&2
          exit 2 ;;
      esac
      exit 0
    fi
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"This file is part of the guardrails (settings, hooks, agents, the working loop, pre-commit or CI). Confirm the change does not weaken a check."}}'
    exit 0
    ;;
esac
exit 0
