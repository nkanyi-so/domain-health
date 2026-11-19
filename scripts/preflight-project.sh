#!/bin/bash
# This project's part of the preflight: confirms every owner action in docs/STANDING.md that a
# script can confirm. Called by .claude/hooks/preflight.sh; can be run alone.
# It reads names and answers, never values: no key, token or account is printed.
# Every gcloud call names the `domain-health` configuration. The machine's default one belongs to
# other work and is never used, changed or read.
# Exit status: the number of MISSING lines (0 is ready).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="domain-health"
MODEL="gpt-6-luna"
missing=0
good() { echo "ok:      $1"; }
warn() { echo "warning: $1"; }
need() { echo "MISSING: $1"; missing=$((missing+1)); }

# A variable from the shell, or else from .env. The value stays in this process.
value_of() {
  local name="$1"
  if [ -n "${!name:-}" ]; then printf '%s' "${!name}"; return; fi
  [ -f "$ROOT/.env" ] || return 0
  sed -n "s/^\(export[[:space:]]\{1,\}\)\{0,1\}$name=//p" "$ROOT/.env" | tail -1 | sed "s/^[\"']//; s/[\"']\$//"
}

# --- toolchains (the same reading make uses) -----------------------------------------------------
if out=$(make -s -C "$ROOT" toolchain 2>/dev/null); then
  printf '%s\n' "$out"
else
  seen=0
  while IFS= read -r line; do
    case "$line" in WARNING:*) need "${line#WARNING: }"; seen=1 ;; *) [ -n "$line" ] && echo "$line" ;; esac
  done <<<"$out"
  # A failure that names no tool means the check itself did not run. That is not a pass.
  [ "$seen" = "1" ] || need "the Node and JDK check did not run (make failed before it could)"
fi

# --- OpenAI: the key answers for the model the evals use (a free call) ----------------------------
key=$(value_of OPENAI_API_KEY)
if [ -z "$key" ]; then
  need "the OpenAI key cannot be checked: OPENAI_API_KEY is not set"
else
  # The header goes in on stdin, so the key is never on a command line another process can list.
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 \
    -H @- "https://api.openai.com/v1/models/$MODEL" 2>/dev/null <<<"Authorization: Bearer $key" || echo 000)
  case "$code" in
    200) good "the OpenAI key answers for $MODEL" ;;
    401) need "OpenAI refused the key (401). Owner: create a new key in the domain-health project" ;;
    403|404) need "the OpenAI key works but cannot use $MODEL ($code). Owner: allow the model in the project" ;;
    *) need "OpenAI did not answer for $MODEL (HTTP $code)" ;;
  esac
fi
unset key

# --- Google Cloud: the project's own configuration, a user login, the project, billing ------------
project=$(value_of GCP_PROJECT_ID)
if ! command -v gcloud >/dev/null 2>&1; then
  need "gcloud is not installed"
elif ! gcloud config configurations describe "$CONFIG" >/dev/null 2>&1; then
  need "there is no gcloud configuration named $CONFIG. Owner: the commands are in docs/STANDING.md"
else
  good "the gcloud configuration $CONFIG exists"
  account=$(gcloud config get-value account --configuration="$CONFIG" 2>/dev/null)
  case "$account" in
    ''|'(unset)') need "the $CONFIG configuration has no login. Owner: gcloud auth login --configuration=$CONFIG" ;;
    *.gserviceaccount.com) need "the $CONFIG configuration is signed in as a service account; it must be a personal user account" ;;
    *) if gcloud auth print-access-token --configuration="$CONFIG" >/dev/null 2>&1; then good "the $CONFIG configuration is signed in with a user account"
       else need "the $CONFIG login has expired. Owner: gcloud auth login --configuration=$CONFIG"; fi ;;
  esac
  configured=$(gcloud config get-value project --configuration="$CONFIG" 2>/dev/null)
  if [ -z "$project" ]; then
    need "the Google Cloud project cannot be checked: GCP_PROJECT_ID is not set"
  elif [ "$configured" != "$project" ]; then
    need "the $CONFIG configuration does not point at GCP_PROJECT_ID. Owner: gcloud config set project <id> --configuration=$CONFIG"
  else
    good "the $CONFIG configuration points at GCP_PROJECT_ID"
    billing=$(gcloud billing projects describe "$project" --configuration="$CONFIG" \
      --format='value(billingEnabled,billingAccountName)' 2>/dev/null)
    case "$billing" in
      True*|true*)
        good "billing is enabled on the project"
        billing_account="${billing##*billingAccounts/}"
        token=$(gcloud auth print-access-token --configuration="$CONFIG" 2>/dev/null)
        allowed=$(curl -sS --max-time 20 -X POST \
          -H @- -H "Content-Type: application/json" \
          -H "x-goog-user-project: $project" \
          -d '{"permissions":["billing.budgets.create"]}' \
          "https://cloudbilling.googleapis.com/v1/billingAccounts/$billing_account:testIamPermissions" \
          2>/dev/null <<<"Authorization: Bearer $token")
        unset token
        case "$allowed" in
          *billing.budgets.create*) good "this login may create budgets on the billing account" ;;
          *) need "this login may not create budgets on the billing account (the \$5 budget alert needs it). Owner: use the billing account's administrator, or grant Billing Account Costs Manager" ;;
        esac ;;
      *) need "billing is not enabled on the project. Owner: gcloud billing projects link <id> --billing-account=<billing> --configuration=$CONFIG" ;;
    esac
  fi
fi

# --- Vercel ------------------------------------------------------------------------------------
if ! command -v vercel >/dev/null 2>&1; then
  need "the vercel command is not installed. Owner: npm i -g vercel@latest"
elif vercel whoami >/dev/null 2>&1; then
  good "vercel whoami answers"
  warn "a script cannot confirm that Vercel's GitHub app can see this repository; the first deploy in Phase 5 will"
else
  need "vercel whoami does not answer. Owner: vercel login"
fi

# --- the name list: only that it exists ------------------------------------------------------------
if [ -s "$HOME/.config/domain-health/names.txt" ]; then good "the name list exists (not read here)"
else warn "no name list at ~/.config/domain-health/names.txt yet; Phase 6 needs it"; fi

exit "$missing"
