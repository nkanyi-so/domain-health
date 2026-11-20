#!/bin/bash
# Runs the backend and the frontend locally, inside the Firestore emulator. Called by `make dev`.
# Backend on http://127.0.0.1:8000, frontend on http://localhost:3000. Ctrl-C stops all three.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
project="${1:-demo-domain-health}"

if [ "${DEV_INSIDE_EMULATOR:-}" != "1" ]; then
  cd "$ROOT/emulator"
  DEV_INSIDE_EMULATOR=1 exec pnpm exec firebase emulators:exec --only firestore --project "$project" \
    "bash '$ROOT/scripts/dev.sh' '$project'"
fi

# The emulator starts empty and nothing runs the daily job locally, so today's snapshots for the
# twelve seeded clients are written first, by the worker's own code with the kept recordings.
(cd "$ROOT/backend" && uv run --frozen python -m domain_health.seeded.dev_snapshots)

pids=()
stop() {
  trap - INT TERM EXIT
  for pid in "${pids[@]}"; do
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null
  done
  wait 2>/dev/null
}
trap stop INT TERM EXIT
(cd "$ROOT/backend" && DOMAIN_HEALTH_DEV=1 exec uv run --frozen uvicorn domain_health.serve:app --reload --host 127.0.0.1 --port 8000) &
pids+=($!)
(cd "$ROOT/frontend" && exec pnpm run dev) &
pids+=($!)
wait
