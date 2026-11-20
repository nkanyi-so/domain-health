#!/bin/bash
# `make seed`: write the twelve seeded clients' names and domains to Firestore. Handled marks
# already there are left alone. With COUNT=<YYYY-MM-DD> it writes nothing and counts that day's
# snapshot documents instead.
#
# The program gets a short-lived access token from the domain-health gcloud configuration in its
# own environment; the token is never printed or stored.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/cloud-common.sh

cd backend
GCP_ACCESS_TOKEN="$(gcloud auth print-access-token)" GCP_PROJECT_ID="$PROJECT" \
  uv run --frozen python -m domain_health.seeded.seed ${COUNT:+--count "$COUNT"}
