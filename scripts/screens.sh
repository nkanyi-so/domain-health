#!/bin/bash
# `make screens`: starts the backend on the Firestore emulator and the frontend, both with the
# development settings, takes the 68 screenshots with their three checks
# (frontend/scripts/screens.mjs), then stops everything it started, whether or not that worked.
# Backend on http://127.0.0.1:8000, frontend on http://localhost:3000, as `make dev` has them, so
# it cannot run beside `make dev`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
project="${1:-demo-domain-health}"

if [ "${SCREENS_INSIDE_EMULATOR:-}" != "1" ]; then
  for port in 3000 8000; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "make screens: port $port is in use. Stop what is listening there (make dev?) first." >&2
      exit 1
    fi
  done
  cd "$ROOT/emulator"
  SCREENS_INSIDE_EMULATOR=1 exec pnpm exec firebase emulators:exec --only firestore --project "$project" \
    "bash '$ROOT/scripts/screens.sh' '$project'"
fi

logs="$(mktemp -d)"
pids=()
stop() {
  status=$?
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] || continue
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
  done
  # A server started through pnpm or uv can outlive its parent. Both ports were free before this
  # script started, so whatever still listens on them is this script's own.
  for port in 3000 8000; do
    lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | xargs kill -TERM 2>/dev/null || true
  done
  for _ in $(seq 1 20); do
    lsof -nP -iTCP:3000 -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.5
  done
  if [ "$status" -ne 0 ]; then
    echo "make screens: failed. The servers' last lines:" >&2
    tail -n 20 "$logs"/*.log >&2 2>/dev/null || true
  fi
  rm -rf "$logs"
  exit "$status"
}
trap stop INT TERM EXIT

# State 16 is a real sign-in on a real page, so the emulator gets today's snapshots first, as
# `make dev` does. The other sixteen states are drawn from the bundled demo views.
(cd "$ROOT/backend" && uv run --frozen python -m domain_health.seeded.dev_snapshots)

(cd "$ROOT/backend" && DOMAIN_HEALTH_DEV=1 exec uv run --frozen uvicorn domain_health.serve:app \
  --host 127.0.0.1 --port 8000) >"$logs/backend.log" 2>&1 &
pids+=($!)
disown
# The development server: the development secrets are refused by a production build, by design.
# No address for "Source", whatever the shell has, so the shots are the same on every machine.
(cd "$ROOT/frontend" && REPO_URL="" exec pnpm exec next dev --port 3000) >"$logs/frontend.log" 2>&1 &
pids+=($!)
disown

wait_for() {
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null --max-time 5 "$1" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "make screens: $1 did not answer within two minutes" >&2
  return 1
}
wait_for http://127.0.0.1:8000/health
wait_for http://localhost:3000/about

cd "$ROOT/frontend"
node scripts/screens.mjs
