#!/bin/bash
# Formats one file with the formatter that owns it. Called by `make format FILE=<path>`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
file="$1"
case "$file" in /*) abs="$file" ;; *) abs="$PWD/$file" ;; esac
[ -f "$abs" ] || { echo "format: no such file: $file" >&2; exit 1; }

case "$abs" in
  "$ROOT"/backend/*.py)
    cd "$ROOT/backend" && uv run --frozen ruff format --quiet "$abs" ;;
  "$ROOT"/frontend/node_modules/*|"$ROOT"/frontend/.next/*|"$ROOT"/frontend/pnpm-lock.yaml|"$ROOT"/frontend/AGENTS.md)
    ;;
  "$ROOT"/frontend/*.ts|"$ROOT"/frontend/*.tsx|"$ROOT"/frontend/*.mjs|"$ROOT"/frontend/*.css|"$ROOT"/frontend/*.json|"$ROOT"/frontend/*.md)
    cd "$ROOT/frontend" && pnpm exec prettier --log-level warn --write "$abs" ;;
esac
