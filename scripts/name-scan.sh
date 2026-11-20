#!/bin/bash
# The name scan: looks for every entry of the owner's name list in the working tree, in every
# commit's changes and message on every branch, and in the branch names. The list is the owner's
# and lives outside the repository; this script never prints an entry, only its line number in
# the list and how many times it was found. Free, local, read-only.
#
#   bash scripts/name-scan.sh [path to the list]      default: ~/.config/domain-health/names.txt
#
# One entry per line; blank lines and lines starting with # are skipped. Matching ignores case
# and is by whole word, so a short entry does not match inside a longer word. Exit 1 on any hit.
set -euo pipefail
cd "$(dirname "$0")/.."
LIST="${1:-$HOME/.config/domain-health/names.txt}"
[ -f "$LIST" ] || { echo "name scan: no list at the path given" >&2; exit 2; }

history="$(mktemp)"; trap 'rm -f "$history"' EXIT
# Every commit reachable from any branch or tag: its subject, body and changed lines. Authors'
# own names and addresses are not part of what is scanned: they are the owner's signature.
git log --all -p --no-color --format='commit %H%n%s%n%b' > "$history"
branches="$(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes refs/tags)"

entries=0; hits=0; line=0
while IFS= read -r entry || [ -n "$entry" ]; do
  line=$((line + 1))
  entry="${entry%$'\r'}"   # a list saved with Windows line endings still matches
  case "$entry" in ''|'#'*) continue ;; esac
  entries=$((entries + 1))
  tree=$( { git grep -I -i -w -F -c -e "$entry" -- . || true; } | awk -F: '{n += $NF} END {print n + 0}')
  past=$( { grep -i -w -F -c -e "$entry" "$history" || true; } )
  refs=$( { printf '%s\n' "$branches" | grep -i -F -c -e "$entry" || true; } )
  if [ "$tree" != 0 ] || [ "$past" != 0 ] || [ "$refs" != 0 ]; then
    hits=$((hits + 1))
    echo "entry on line $line of the list: tree $tree, history $past, branch names $refs"
  fi
done < "$LIST"
echo "name scan: $entries entries, $(git rev-list --all --count) commits, $(printf '%s\n' "$branches" | wc -l | tr -d ' ') branch and tag names; $hits with a hit"
[ "$hits" = 0 ]
